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
import sys

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
    # @TODO:
    # Parar de usar enable_usermap, pensar em uma outra forma de possuir uma "memória volátil"
    # para os comandos usarem dependendo do contexto
    def __init__(self, bot, permissionlevel: PermissionLevel=PermissionLevel.NONE, hidden: bool=False, enable_usermap: bool=False, **kwargs):
        super().__init__(bot)

        self.update_info(kwargs)

        self.permissionlevel = permissionlevel
        self.hidden = hidden

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
    def __init__(self, bot, name: str, command: str, permissionlevel: PermissionLevel=PermissionLevel.NONE, hidden: bool=False):
        super().__init__(bot, permissionlevel=permissionlevel, enable_usermap=False, hidden=hidden, name=name)

        self.command = command

    def get_usage_text(self):
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

class ModuleHook:
    def __init__(self, bot):
        self.bot = bot
        self.binded_events_ids = []

    def bind_event(self, eventname: str, coroutinefunc: callable, name: str=None):
        self.binded_events_ids.append(
            (
                eventname,
                self.bot.client.register_event(
                    eventname,
                    coroutinefunc,
                    name=name
                )
            )
        )

    def clear_binded_events(self):
        for event, eid in self.binded_events_ids:
            self.bot.client.remove_event(
                event,
                eid
            )

    def get_guild_settings_manager(self):
        assert self.bot.guildsettings

        return self.bot.guildsettings

    def run(self):
        raise NotImplementedError()

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

    async def on_member_join(self, member: discord.Member):
        await self.dispatch_event('on_member_join', member=member)

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
            asyncio.create_task(
                coroutine(kwargs)
            )

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
        # Lista de hooks acoplados
        self.hooks = []

        # Inicialização de tudo
        self.load_all_modules()

        # Nosso gerênciador de variáveis por Guild.
        self.guildsettings = GuildSettingsManager(
            self, 
            self.config.get('guild_settings', {})
        )

        # Objeto de conexão de banco de dados ativo no momento.
        self.active_database = None

        # Intervalo que fica rodando de fundo para a troca de atividades.
        self.playing_interval = None

    def load_all_modules(self):
        self.commands.clear()

        for hook in self.hooks:
            hook.clear_binded_events()

        self.hooks.clear()

        # Popula o dicionário acima, procurando os modulos em NAVI_PATH/modules e encontra comandos e hooks
        self.load_modules(f'{self.curr_path}/modules', force_reload=True)
        # Carrega os comandos interpretados definidos na chave específicada.
        self.load_interpreted_commands('interpreted_commands')

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

    def load_modules(self, dirpath: str, force_reload: bool=False):
        with os.scandir(dirpath) as iterator:
            for file in iterator:
                if file.name.endswith('.py') and file.is_file():
                    module_str = f"{dirpath[len(os.path.dirname(dirpath)) + 1:].replace('/', '.')}.{file.name[:-3]}"
                    # Isso pode falhar, caso falhe, apenas avise o log e ignore o modulo.
                    try:
                        if module_str in sys.modules:
                            mod = importlib.reload(sys.modules[module_str])
                        else:
                            # Caso o modulo já esteja importando, essa call é ignorada, porém ainda recebemos o objeto module de retorno.
                            # Isso não é para falhar, caso falhe, será durante a inicialização e portanto encontramos um erro no código do modulo.
                            mod = importlib.import_module(module_str)
                        
                    except Exception as e:
                        logging.exception(f'LOAD_MODULES, failed to load module {module_str}, skipping broken module: {type(e).__name__}: {e}')
                        continue
                    finally:
                        self.load_objects_from_module(mod)

    def load_objects_from_module(self, mod):
        logging.info(f"Attempting to load commands from module: {mod}")
        
        # Não gosto muito dessa lambda, mas pore enquanto vamos filtrar assim...
        for obj in inspect.getmembers(mod, lambda x: inspect.isclass(x) and (is_subclass(x, BotCommand) and x != BotCommand and x != InterpretedCommand or is_subclass(x, ModuleHook) and x != ModuleHook)):
            cmd = obj[1](self)

            if is_instance(cmd, BotCommand):
                assert inspect.iscoroutinefunction(getattr(cmd, 'run'))
                
                self.commands[cmd.name.lower()] = cmd

                for alias in cmd.aliases:
                    self.commands[alias.lower()] = CommandAlias(cmd)

                logging.info(f"Successfully loaded a new command: {cmd.name} ({mod.__name__}.{type(cmd).__name__})")
            else:
                assert is_instance(cmd, ModuleHook)
                
                self.hooks.append(cmd)

                cmd.run()

                logging.info(f"Successfully loaded a new hook: {mod.__name__}.{type(cmd).__name__} ({cmd})")

    def add_interpreted_command(self, command: InterpretedCommand):
        logging.info(f"Adding interpreted command: {command.name} ({command})")

        if command.name in self.commands:
            if isinstance(self.commands[command.name], InterpretedCommand):
                self.commands[command.name] = command
            else:
                raise BotError(f'O comando {command.name} já existe e não pode ser substituido.')
        else:
            self.commands[command.name] = command

    def remove_interpreted_command(self, name: str):
        if name in self.commands:
            command = self.commands[name]
            
            if isinstance(command, InterpretedCommand):
                logging.info(f"Removing interpreted command: {command.name} ({command})")

                del self.commands[name]
            else:
                raise BotError(f'O comando {command.name} já existe e não pode ser substituido.')

            return command
        else:
            raise BotError(f'O comando {name} não existe.')

    def load_interpreted_commands(self, keystr: str):
        for command in self.config.get(keystr, []):
            self.add_interpreted_command(
                InterpretedCommand(
                    self,
                    command['name'],
                    command['value']
                )
            )

    async def reload_all_modules(self):
        logging.info(f"Reloading configuration file and all modules...")

        # @TODO: Verificar se isso aqui é seguro mostrar para o usuário.
        # Se isso falhar, voltará o Exception para o HotReload
        self.config.load()

        self.load_all_modules()

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

    def has_permission_level(self, permissionlevel: PermissionLevel, ctx: Context):
        return self.rate_author_permission_level(ctx).value >= permissionlevel.value

    def rate_author_permission_level(self, ctx: Context):
        assert ctx.author
        assert ctx.guild

        permlevel = PermissionLevel.NONE

        if ctx.author.id in self.config.get('global.owner_ids', []):
            permlevel =  PermissionLevel.BOT_OWNER
        else:
            permissions = ctx.channel.permissions_for(ctx.author)

            if permissions.kick_members or permissions.ban_members:
                permlevel = PermissionLevel.GUILD_MOD
            if permissions.administrator:
                permlevel = PermissionLevel.GUILD_ADMIN
            if ctx.guild.owner == ctx.author:
                permlevel = PermissionLevel.GUILD_OWNER

        return permlevel

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

    async def get_bot_prefix(self, ctx: Context):
        assert ctx.guild

        gsm = self.guildsettings
        var = None

        try:
            var = await gsm.get_guild_variable(ctx.guild.id, 'bot_prefix')
        except DatabaseError:
            pass

        if var and var.get_value():
            return var.get_value()
            
        return self.config.get('global.prefix', ';;')

    async def reset_bot_prefix(self, ctx: Context):
        assert ctx.guild

        if not self.has_permission_level(PermissionLevel.GUILD_MOD, ctx):
            raise PermissionLevelError(f'Você não possui um nível de permissão igual ou superior à `{PermissionLevel.GUILD_MOD.name}`  para poder realizar esta ação.')

        gsm = self.guildsettings

        var = await gsm.get_guild_variable(ctx.guild.id, 'bot_prefix')
        
        if var:
            return await gsm.remove_guild_variable(var)
        else:
            raise Exception(f'Variável `bot_prefix` não encontrado no contexto da Guild atual.')

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

        prefix = await self.get_bot_prefix(ctx)

        if not ctx.message.content.startswith(prefix):
            if self.client.user in ctx.message.mentions:
                if 'resetprefix' in ctx.message.content:
                    try:
                        if await self.reset_bot_prefix(ctx):
                            await ctx.reply(ReactionType.SUCCESS)
                        else:
                            await ctx.reply(ReactionType.FAILURE)
                    except PermissionLevelError as e:
                        await ctx.reply(e)
                    except Exception as e:
                        logging.exception(f'RECEIVE_MESSAGE: {type(e).__name__}: {e}')
                        await ctx.reply(ReactionType.FAILURE)
                else:
                    await ctx.reply(f'Por acaso esqueceu o prefixo do bot para esta Guild?\n\nO prefixo atual está configurado para `{prefix}`\n\nPara voltar o prefixo ao padrão, mencione o bot novamente com a palavra `resetprefix`.')

            return
        else:
            resolve_subcommands = True
            if ctx.message.content.startswith(prefix + '!'):
                prefix += '!'
                resolve_subcommands = False
        
        await self.handle_command_parse(ctx, ctx.message.content[len(prefix):], resolve_subcommands)

    async def handle_command_parse(self, ctx: Context, content: str, resolve_subcommands: bool=True):
        parser = CommandParser(
            content,
            resolve_subcommands
        )
 
        try:
            pipeline = parser.parse()

            output = await self.handle_pipeline_execution(ctx, pipeline)

            if output:
                await ctx.reply(output)
        except (ParserError, BotError, PermissionLevelError, CommandError, DatabaseError) as e:
            # Exception "amigável", envie isso no contexto atual de volta para o usuário
            await ctx.reply(e)

    async def handle_pipeline_execution(self, ctx: Context, pipeline, activator_args: list=None, activator_flags: dict=None):
        pipeline_output = ''
        
        for command in pipeline:
            handler = self.commands.get(command.cmd.lower(), None)

            if handler:
                handler = handler.origin if isinstance(handler, CommandAlias) else handler

                if not self.has_permission_level(handler.permissionlevel, ctx):
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
    def __init__(self, bot: Bot, default_values: dict={}, cache_timelimit: int=600):
        self.bot = bot
        self.default_values = default_values
        self.guildmap = {}
        self.cache_timelimit = cache_timelimit

    async def get_database_connection(self):
        return await self.bot.get_database_connection()

    async def get_cacheable_guild_variable(self, guildid: int, key: str):
        dal = GuildVariableDAL(await self.get_database_connection())

        if not guildid in self.guildmap:
            self.guildmap[guildid] = {}

        if key in self.guildmap[guildid] and time.time() - self.guildmap[guildid][key].fetched_at < self.cache_timelimit:
            currvar = self.guildmap[guildid][key]
        else:
            currvar = await dal.get_variable(guildid, key)

            if currvar:
                currvar.fetched_at = time.time()
                self.guildmap[guildid][key] = currvar

        return currvar
        
    async def get_guild_variable(self, guildid: int, key: str):
        var = await self.get_cacheable_guild_variable(guildid, key)

        if not var:
            default = self.default_values.get(key, None)

            if default != None:
                var = GuildVariable( 
                    guildid,
                    key,
                    default,
                    None
                )

        return var

    async def get_all_guild_variables(self, guildid: int):
        dal = GuildVariableDAL(await self.get_database_connection())

        if not guildid in self.guildmap:
            self.guildmap[guildid] = {}

        tm = time.time()
        for var in await dal.get_all_variables(guildid):
            var.fetched_at = tm
            self.guildmap[guildid][var.key] = var

        dictview = dict(self.guildmap[guildid])
        for key, value in self.default_values.items():
            if not key in dictview:
                dictview[key] = GuildVariable( 
                    guildid,
                    key,
                    value,
                    None
                )

        return dictview

    async def update_guild_variable(self, variable: GuildVariable):
        dal = GuildVariableDAL(await self.get_database_connection())

        if variable.key in self.guildmap[variable.guildid]:
            # Já temos no banco
            return await dal.update_variable(variable)
        else:
            ok = await dal.create_variable(variable)

            if ok:
                self.guildmap[variable.guildid][variable.key] = variable
                variable.fetched_at = time.time()

            return ok

    async def remove_guild_variable(self, variable: GuildVariable):
        dal = GuildVariableDAL(await self.get_database_connection())

        ok = await dal.remove_variable(variable)

        if ok and variable.key in self.guildmap[variable.guildid]:
            del self.guildmap[variable.guildid][variable.key]

        return ok

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