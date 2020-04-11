# Client module
import discord
import asyncio
import logging
import json
import os
import importlib
import inspect
import time
import traceback
import databases
import re

from enum import Enum, auto

from navibot.parser import CommandParser
from navibot.util import is_instance, is_subclass
from navibot.errors import *
from navibot.database.dal import GuildVariableDAL
from navibot.database.models import GuildVariable

class PermissionLevel(Enum):
    NONE = auto()
    GUILD_MOD = auto()
    GUILD_ADMIN = auto()
    GUILD_OWNER = auto()
    BOT_OWNER = auto()

class ReactionType(Enum):
    SUCCESS = '✅'
    FAILURE = '❌'

class Context:
    def __init__(self, bot, channel: discord.TextChannel, guild: discord.Guild=None, author: discord.User=None, message: discord.Message=None):
        self.bot = bot
        self.channel = channel
        self.author = author
        self.guild = guild
        self.message = message

    def create_response_embed(self):
        return self.bot.create_response_embed(self)

    async def reply(self, response):
        if isinstance(response, str) or isinstance(response, list):
            embed = self.create_response_embed()
            embed.description = ' '.join(response) if isinstance(response, list) else response
            
            return await self.channel.send(embed=embed)

        elif isinstance(response, discord.Embed):
            return await self.channel.send(embed=response)

        elif isinstance(response, Slider):
            return await response.send()

        elif isinstance(response, ReactionType):
            if not self.message:
                raise AttributeError('É preciso vincular uma mensagem a este contexto para poder adicionar uma reação.')

            return await self.message.add_reaction(response.value)

        elif isinstance(response, Exception):
            embed = self.create_response_embed()
            embed.description = f':red_circle: **{type(response).__name__}**: {response}'

            return await self.channel.send(embed=embed)

        else:
            raise ValueError('Não é possível responser a este contexto, pois o parâmetro informado não é de um tipo conhecido.')

class Command:
    def __init__(self, bot):
        self.bot = bot
        self.name = type(self).__name__.lower()
        self.description = 'Descrição não disponível.'
        self.usage = ''
        self.aliases = []

    def get_usage_text(self):
        return f"{self.description}\n\n`{self.name} {self.usage}`"

    def update_info(self, new_info: dict):
        for key, value in new_info.items():
            currattr = getattr(self, key, None)

            if currattr is not None:
                if isinstance(value, type(currattr)):
                    setattr(self, key, value)
                else:
                    raise TypeError("É preciso informar um atributo básico com o mesmo tipo.")

    async def run(self, args: list, flags: dict):
        raise NotImplementedError()

class BotCommand(Command):
    def __init__(self, bot, permissionlevel: PermissionLevel=PermissionLevel.NONE, enable_usermap: bool=False, **kwargs):
        super().__init__(bot)

        self.update_info(kwargs)

        self.permissionlevel = permissionlevel
        self.enable_usermap = enable_usermap
        
        if self.enable_usermap:
            self.usermap = dict()

    def create_response_embed(self, ctx: Context):
        return self.bot.create_response_embed(ctx)

    def get_usage_embed(self, ctx: Context):
        embed = self.create_response_embed(ctx)

        embed.description = self.get_usage_text()
        embed.title = f"{self.name}" if not self.aliases else f"{self.name} {self.aliases}"

        return embed

    def get_user_storage(self, author: discord.User):
        assert self.enable_usermap

        try:
            return self.usermap[author.id]
        except KeyError:
            self.usermap[author.id] = list()
            return self.usermap[author.id]

    def get_guild_settings_manager(self):
        assert self.bot.guildsettings

        return self.bot.guildsettings

    async def run(self, ctx: Context, args: list, flags: dict):
        raise NotImplementedError()

class InterpretedCommand(BotCommand):
    def __init__(self, bot, name: str, command: str, permissionlevel: PermissionLevel=PermissionLevel.NONE):
        super().__init__(bot, permissionlevel=permissionlevel, enable_usermap=False, name=name)

        self.command = command

    def get_usage_text(self, ctx: Context):
        return f'O comando `{self.name}` é interpretado e pode ser traduzido para:\n\n`{self.command}`'

    async def run(self, ctx: Context, args: list, flags: dict):
        p = CommandParser(self.command)

        pipeline = p.parse()

        # Executa uma PIPELINE para executar este comando interpretado,
        # os parâmetros activator_args e activator_flags são preservados pois
        # apontam para os args e flags originais recebidos pelo comando interpretado.
        return await self.bot.handle_pipeline_execution(
            ctx, 
            pipeline, 
            activator_args=args, 
            activator_flags=flags
        )

class CommandAlias:
    def __init__(self, origin: BotCommand):
        self.origin = origin

class TimeoutContext:
    def __init__(self, waitfor: int, callable: callable, callback: callable=None, **kwargs):
        self.waitfor = waitfor
        self.callable = callable
        self.callback = callback
        self.kwargs = kwargs
        self.running_task = None
        self.caught_exception = None

    async def run(self):
        try:
            await asyncio.sleep(self.waitfor)
            await self.callable(self, self.kwargs)

            if self.callback:
                await self.callback(self, self.kwargs)
        except Exception as e:
            self.caught_exception = e
        finally:
            self.running_task = None

    def create_task(self):
        assert not self.running_task

        self.caught_exception = None
        self.running_task = asyncio.get_running_loop().create_task(self.run())


class IntervalContext(TimeoutContext):
    def __init__(self, waitfor: int, callable: callable, max_count: int=0, callback: callable=None, ignore_exception: bool=False, **kwargs):
        super().__init__(waitfor, callable, callback=callback, **kwargs)

        self.ignore_exception = ignore_exception
        self.max_count = max_count
        self.safe_halt = False
        self.run_count = 0
    
    async def run(self):
        time_start = 0
        time_delta = 0

        try:
            while not self.safe_halt and (self.max_count <= 0 or self.run_count < self.max_count):
                time_start = time.time()
                
                try:
                    self.run_count += 1
                    await self.callable(self, self.kwargs)
                except Exception as e:
                    if not self.ignore_exception:
                        raise e
                finally:
                    time_delta = time.time() - time_start
                    await asyncio.sleep(self.waitfor - time_delta)    
        except Exception as e:
            self.caught_exception = e
        finally:
            self.running_task = None

            if self.callback:
                await self.callback(self, self.kwargs)

class Client(discord.Client):
    def __init__(self):
        super().__init__()
        
        self.listeners = {}

    async def on_message(self, message: discord.Message):
        await self.dispatch_event('message', message=message)

    async def on_ready(self):
        await self.dispatch_event('ready')

    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        await self.dispatch_event('reaction_add', reaction=reaction, user=user)

    def listen(self, token):
        self.run(token)

    def register_event(self, eventname: str, coroutinefunc: callable, name: str=None):
        assert asyncio.iscoroutinefunction(coroutinefunc)

        eid = coroutinefunc.__name__ if name is None else name

        if not eventname in self.listeners:
            self.listeners[eventname] = dict()

        self.listeners[eventname][eid] = coroutinefunc
        
        return eid

    def remove_event(self, eventname: str, eid: str):
        del self.listeners[eventname][eid]

    async def dispatch_event(self, eventname: str, **kwargs):
        if not eventname in self.listeners:
            return

        for coroutine in self.listeners[eventname].values():
            await coroutine(kwargs)

class Config:
    def __init__(self, configfile: str):
        self.kvalues = {}
        self.path = configfile

    def load(self):
        with open(self.path, 'r', encoding='utf-8') as f:
            self.kvalues = json.loads(''.join(f.readlines()))

    def get(self, keystr: str, default=None):
        keys = keystr.split('.')
        curr = self.kvalues

        if len(keys) <= 0:
            return

        try:
            for i in keys:
                curr = curr[i]
        except KeyError:
            return default

        return curr

class Bot:
    def __init__(self, path: str=None, logfile: str=None, loglevel=logging.DEBUG):
        logging.basicConfig(
            filename=logfile, 
            format="[%(asctime)s] <%(levelname)s> %(message)s", 
            datefmt="%d/%m/%Y %H:%M:%S", 
            level=loglevel
        )

        # Caminho base do bot, é utilizado como referência para procurar modulos
        self.curr_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if not path else path
        
        # Intervalo que fica rodando de fundo para a troca de atividades.
        self.playing_interval = None

        # Nosso objeto para carregar valores do arquivo de configurações
        self.config = Config(
            f'{self.curr_path}/release/config.json'
        )

        self.config.load()
        
        self.client = Client()

        # Prepara o handler para receber comandos em mensagens
        self.client.register_event(
            'message', 
            self.receive_message
        )
        
        # Vai efetuar inicializações
        self.client.register_event(
            'ready', 
            self.receive_ready
        )

        # Dicionário de comandos
        self.commands = {}

        # Popula o dicionário acima, procurando os modulos em NAVI_PATH/modules
        self.load_modules(f'{self.curr_path}/modules')
        
        # Carrega os comandos interpretados definidos na chave específicada.
        self.load_interpreted_commands('interpreted_commands')
        
        # Objeto de conexão de banco de dados ativo no momento.
        self.active_database = None

        # Nosso gerênciador de variáveis por Guild.
        self.guildsettings = GuildSettingsManager(
            self, 
            defaultvalues=self.config.get('guild_settings', default={})
        )

    async def get_database_connection(self):
        if not self.active_database:
            self.active_database = databases.Database(
                self.config.get('database.connection_string')
            )

        if not self.active_database.is_connected:
            try:
                await self.active_database.connect()
            except Exception as e:
                logging.error(f'Connecting to the database failed: {e}')

                raise DatabaseError('Não foi possível conectar-se à base de dados.')
        
        return self.active_database

    def load_modules(self, dirpath: str):
        with os.scandir(dirpath) as iterator:
            for file in iterator:
                if file.name.endswith('.py') and file.is_file():
                    mod = importlib.import_module(f"{dirpath[len(os.path.dirname(dirpath)) + 1:].replace('/', '.')}.{file.name[:-3]}")
                    self.load_commands_from_module(mod)

    def load_commands_from_module(self, mod):
        logging.info(f"Attempting to load commands from module: {mod}")
        
        for obj in inspect.getmembers(mod, lambda x: inspect.isclass(x) and is_subclass(x, BotCommand) and x != BotCommand and x != InterpretedCommand):
            cmd = obj[1](self)

            assert inspect.iscoroutinefunction(getattr(cmd, 'run'))

            self.commands[cmd.name.lower()] = cmd

            for alias in cmd.aliases:
                self.commands[alias.lower()] = CommandAlias(cmd)

            logging.info(f"Successfully loaded a new command: {cmd.name} ({mod.__name__}.{type(cmd).__name__})")

    def add_interpreted_command(self, command: InterpretedCommand):
        logging.info(f"Adding interpreted command: {command.name} ({command})")

        if command.name in self.commands:
            if isinstance(self.commands[command.name], InterpretedCommand):
                self.commands[command.name] = command
            else:
                raise Exception(f'O comando {command.name} já existe e não pode ser substituido.')
        else:
            self.commands[command.name] = command

    def load_interpreted_commands(self, keystr: str):
        for command in self.config.get(keystr, []):
            self.add_interpreted_command(
                InterpretedCommand(
                    self,
                    command['name'],
                    command['value']
                )
            )

    def listen(self):
        self.client.listen(self.config.get('global.token'))

    def create_response_embed(self, ctx: Context):
        assert ctx.author

        return discord.Embed( 
            color=discord.Color.magenta()
        ).set_footer(
            text=ctx.author.name, 
            icon_url=ctx.author.avatar_url_as(size=32)
        )

    def extract_mentions_from(self, args: list, flags: dict, ctx: Context):
        assert ctx.guild

        flags['mentions'] = []
        flags['channel_mentions'] = []
        flags['role_mentions'] = []

        for arg in args:
            # Padrão das mentions do Discord podem ser encontradas aqui:
            # https://discordapp.com/developers/docs/reference#message-formatting

            if re.findall('^<(@[!&]?|#)[0-9]+>$', arg):
                try:
                    num = int(re.findall('[0-9]+', arg)[0])
                except ValueError:
                    # Impossível de acontecer
                    raise BotError('Recebido menção como argumento porém o identificador é inválido.')

                found = None
                if arg[1] == '@':
                    if arg[2] == '&':
                        dest_list = flags['role_mentions']
                        found = ctx.guild.get_role(num)
                    else:
                        # Usuario e Usuario (Apelido)
                        dest_list = flags['mentions']
                        found = ctx.guild.get_member(num)
                elif arg[1] == '#':
                    dest_list = flags['channel_mentions']
                    found = ctx.guild.get_channel(num)

                if found:
                    dest_list.append(found)
                else:
                    raise BotError(f'O objeto `{num}` mencionado não foi encontrado na Guild atual.')

    async def set_playing_game(self, playingstr: str, status=discord.Status, afk: bool=False):
        await self.client.change_presence(activity=discord.Game(playingstr), status=status, afk=afk)

    async def receive_ready(self, kwargs):
        logging.info(f"Successfully logged in")

        if self.playing_interval is None:
            self.playing_interval = IntervalContext(
                self.config.get('global.playing_delay', 60),
                self.callable_update_playing,
                ignore_exception=True
            )

            self.playing_interval.create_task()

    async def receive_message(self, kwargs):
        message = kwargs.get('message')

        # Somente aceita mensagens que não são do próprio bot, que não são de outros bots e que está vindo de um canal de texto de uma Guild.
        if message.author == self.client.user or message.author.bot or not isinstance(message.channel, discord.TextChannel):
            return

        # Contexto utilizado daqui em diante...
        ctx = Context(
            self,
            message.channel,
            message.guild,
            message.author,
            message
        )

        prefix = self.config.get('global.prefix', ';;')

        if not ctx.message.content.startswith(prefix):
            return
        
        parser = CommandParser(
            ctx.message.content[len(prefix):]
        )
 
        try:
            pipeline = parser.parse()

            output = await self.handle_pipeline_execution(ctx, pipeline)

            if output:
                await ctx.reply(output)
        except (ParserError, BotError, PermissionLevelError, CommandError, DatabaseError) as e:
            # Exception "amigável", envie isso no contexto atual de volta para o usuário
            await ctx.reply(e)

    def has_permission_level(self, command: BotCommand, ctx: Context):
        assert ctx.author
        assert ctx.guild

        if command.permissionlevel is PermissionLevel.NONE:
            return True
        elif command.permissionlevel is PermissionLevel.BOT_OWNER:
            return ctx.author.id in self.config.get('global.owner_ids', [])
        else:
            currlevel = None
            permissions = ctx.channel.permissions_for(ctx.author)

            if permissions.kick_members or permissions.ban_members:
                currlevel = PermissionLevel.GUILD_MOD
            
            if permissions.administrator:
                currlevel = PermissionLevel.GUILD_ADMIN

            if ctx.guild.owner == ctx.author:
                currlevel = PermissionLevel.GUILD_OWNER
            
            return currlevel.value >= command.permissionlevel.value if currlevel else False

    async def handle_pipeline_execution(self, ctx: Context, pipeline, activator_args: list=None, activator_flags: dict=None):
        pipeline_output = ''
        
        for command in pipeline:
            handler = self.commands.get(command.cmd.lower(), None)

            if handler:
                handler = handler.origin if isinstance(handler, CommandAlias) else handler

                if not self.has_permission_level(handler, ctx):
                    raise PermissionLevelError(f"Você não possui um nível de permissão igual ou superior à `{handler.permissionlevel.name}`")

                args = command.args
                flags = command.flags

                for c in range(len(args)):
                    arg = args[c]

                    # Se o argumento é uma lista, quer dizer que é uma string literal, veja se precisa processar algum comando no meio dela.
                    if isinstance(arg, list):
                        # Para cada 'pedaço' dentro dessa string literal
                        for i in range(len(arg)):
                            chunk = arg[i]

                            # Se encontrarmos um pedaço que seja uma lista, temos uma outra PIPELINE, execute ela recursivamente antes para termos o resultado como uma string.
                            if isinstance(chunk, list):
                                arg[i] = await self.handle_pipeline_execution(ctx, chunk, activator_args=activator_args, activator_flags=activator_flags)

                                # Recebemos uma string ou lista de strings?
                                if not isinstance(arg[i], str) and not isinstance(arg[i], list):
                                    raise BotError(f"O comando `{chunk[0].cmd}` não retornou dados compatíveis para utilizar de argumento...")
                                elif isinstance(arg[i], list):
                                    # As listas precisam reduzidas em simples strings para poder continuarem como argumento deste comando.
                                    arg[i] = ' '.join(arg[i])

                        # Retorne todos os pedaços a um só argumento string único.
                        args[c] = ''.join(arg)

                # Se estamos prestes a passar uma saída de outro comando na PIPELINE para este atual, precisa ser um tipo válido.
                if not isinstance(pipeline_output, str) and not isinstance(pipeline_output, list):
                    raise BotError(f"O comando `{command.cmd}` recebeu uma saída inválida, abortando...")
                
                # Continue o processamento da PIPELINE.
                pipeline_output = await self.handle_command_execution(
                    handler, 
                    ctx, 
                    args, 
                    flags, 
                    received_pipe_data=pipeline_output, 
                    activator_args=activator_args, 
                    activator_flags=activator_flags
                )
            else:
                raise BotError(f"O comando `{command.cmd}` não existe, abortando...")

        # Terminando todo o processamento desta PIPELINE, volte para cima.
        return pipeline_output

    async def handle_command_execution(self, command: BotCommand, ctx: Context, args: list, flags: dict, received_pipe_data='', activator_args: list=None, activator_flags: dict=None):
        logging.info(f'Handling execution of {command.name}: {command}')

        output = None

        # Se estamos requisitando apenas ajuda.
        if 'h' in flags or 'help' in flags:
            output = command.get_usage_embed(ctx)
        else:
            # Precisamos definir quem são as menções recebidas por argumento (não posso depender de message.mentions, etc...)
            self.extract_mentions_from(args, flags, ctx)

            # Se temos dados vindos da PIPELINE, aumentar os argumentos desse comando atual.
            if received_pipe_data:
                if isinstance(received_pipe_data, list):
                    args.extend(received_pipe_data)
                else:
                    args.append(received_pipe_data)

            # Se temos argumentos vindos de um outro comando ativador (Ex: InterpretedCommand)
            if activator_args != None:
                    flags['activator_args'] = activator_args

            # Se temos argumentos vindos de um outro comando ativador (Ex: InterpretedCommand)
            if activator_flags != None:
                flags['activator_flags'] = activator_flags

            try:
                output = await command.run(
                    ctx, 
                    args, 
                    flags
                )
            except CommandError as e:
                # Unica forma aceitável de Exception dentro de um comando.
                logging.warn(f'Command {command.name} threw an error: {e}')
                raise e
            except (ParserError, BotError) as e:
                # Essas Exceptions só são possíveis de serem recebidas caso estejamos executando um InterpretedCommand
                assert isinstance(command, InterpretedCommand)
                raise e
            except DatabaseError as e:
                # Exception relacionada a conexão com o banco de dados.
                raise e
            except Exception as e:
                # Por padrão, não mostrar Exceptions vindo de comandos, deixar isso para o console.
                logging.exception(f'Uncaught exception thrown while running {command.name}: {e}\n\n{traceback.format_exc()}')

        return output

    async def callable_update_playing(self, intervalcontext: IntervalContext, kwargs: dict):
        index = kwargs.get('index', 0)
        playing_list = self.config.get('global.playing', None)

        if not playing_list or len(playing_list) == 1:
            intervalcontext.safe_halt = True

            if playing_list:
                await self.set_playing_game(playing_list[index])
        else:
            if index >= len(playing_list):
                index = 0

            await self.set_playing_game(playing_list[index])
            kwargs['index'] = index + 1

class GuildSettingsManager:
    def __init__(self, bot: Bot, defaultvalues: dict={}):
        self.bot = bot
        self.defaultvalues = defaultvalues
        self.guildmap = {}

    async def get_database_connection(self):
        return await self.bot.get_database_connection()

    async def initialize_guild_variables(self, guildid: int):
        if not guildid in self.guildmap:
            self.guildmap[guildid] = dict(self.defaultvalues)

            for key, value in self.guildmap[guildid].items():
                self.guildmap[guildid][key] = GuildVariable(
                    guildid,
                    key,
                    value,
                    None
                )

            dal = GuildVariableDAL(await self.get_database_connection())
            
            for variable in await dal.get_all_variables(guildid):
                self.guildmap[variable.guildid][variable.key] = variable

    async def get_guild_variable(self, guildid: int, key: str, default=None):
        await self.initialize_guild_variables(guildid)
        
        return self.guildmap[guildid].get(key, default)

    async def get_guild_variables(self, guildid: int):
        await self.initialize_guild_variables(guildid)
        
        return self.guildmap[guildid]

    async def update_guild_variable(self, variable: GuildVariable):
        dal = GuildVariableDAL(await self.get_database_connection())

        ok = await dal.update_variable(variable)

        if not ok:
            # Não existe ainda, crie
            return await dal.create_variable(variable)
        else:
            return ok

    async def remove_guild_variable(self, variable: GuildVariable):
        # Isso vai voltar para o valor padrão
        dal = GuildVariableDAL(await self.get_database_connection())

        if await dal.remove_variable(variable):
            variable.set_value(self.defaultvalues[variable.key])

            return True

        return False

class Slider:
    def __init__(self, bot: Bot, ctx: Context, items: list, reaction_right: str=r'▶️', reaction_left: str=r'◀️', restricted: bool=False, startat: int=0, timeout: int=60):
        assert items
        
        self.bot = bot
        self.ctx = ctx

        self.items = items
        
        self.reaction_right = reaction_right
        self.reaction_left = reaction_left
        
        self.restricted = restricted
        self.current_index = startat
        self.timeout = timeout

        self.sent_message = None
        self.last_activity = 0
        self.registered_event_id = None
        self.caught_exception = None

    def forward(self):
        self.current_index += 1

        if self.current_index >= len(self.items):
            self.current_index = 0

    def backward(self):
        self.current_index -= 1

        if self.current_index < 0:
            self.current_index = len(self.items) - 1

    def get_current_item(self):
        cpy = self.items[self.current_index].copy()

        cpy.set_footer(text=f"{cpy.footer.text} <{self.current_index + 1}/{len(self.items)}>", icon_url=cpy.footer.icon_url)
        
        return cpy

    async def callable_on_add_reaction(self, kwargs):
        reaction = kwargs['reaction']
        user = kwargs['user']

        assert self.sent_message and self.registered_event_id

        if reaction.message.id != self.sent_message.id or user == self.bot.client.user or (self.restricted and user != self.ctx.author):
            return

        if reaction.emoji == self.reaction_right:
            self.forward()
        elif reaction.emoji == self.reaction_left:
            self.backward()
        else:
            return

        curritem = self.get_current_item()

        try:
            await self.sent_message.edit(embed=curritem)
        except (discord.Forbidden, discord.HTTPException) as e:
            self.caught_exception = e
        finally:
            if self.caught_exception:
                self.bot.client.remove_event(
                    "reaction_add", 
                    self.registered_event_id
                )
            else:
                self.last_activity = time.time()

    async def send(self):
        curritem = self.get_current_item()

        try:
            self.sent_message = await self.ctx.reply(curritem)
        except (discord.Forbidden, discord.HTTPException) as e:
            self.caught_exception = e

        if not self.caught_exception:
            if len(self.items) == 1:
                return
            else:
                self.registered_event_id = self.bot.client.register_event(
                    'reaction_add', 
                    self.callable_on_add_reaction, 
                    name=f'slider_send_{self.sent_message.id}'
                )

            await asyncio.gather(
                self.sent_message.add_reaction(self.reaction_left),
                self.sent_message.add_reaction(self.reaction_right)
            )

            self.last_activity = time.time()

            while time.time() - self.last_activity <= self.timeout:
                await asyncio.sleep(self.timeout)

            if not self.caught_exception:
                self.bot.client.remove_event(
                    "reaction_add", 
                    self.registered_event_id
                )