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

class Command:
    def __init__(self, bot):
        assert isinstance(bot, Bot)

        self.bot = bot
        self.name = type(self).__name__.lower()
        self.description = 'Descrição não disponível.'
        self.usage = '{name}'
        self.aliases = []

    def update_info(self, new_info):
        for key, value in new_info.items():
            currattr = getattr(self, key, None)
            if currattr is not None:
                if isinstance(value, type(currattr)):
                    setattr(self, key, value)
                else:
                    raise TypeError("É preciso informar um atributo básico com o mesmo tipo.")

    async def run(self, args, flags):
        raise NotImplementedError()

class BotCommand(Command):
    def __init__(self, bot, permissionlevel=PermissionLevel.NONE, enable_usermap=False, **kwargs):
        super().__init__(bot)

        self.update_info(kwargs)

        self.permissionlevel = permissionlevel
        self.enable_usermap = enable_usermap
        if self.enable_usermap:
            self.usermap = dict()

    def create_response_embed(self, message, description=''):
        return self.bot.create_response_embed(message, description)

    def get_usage_embed(self, message):
        text = f"{self.description}\n\n`{self.usage.format(name=self.name)}`"
        embed = self.create_response_embed(message, text)
        embed.title = f"{self.name}" if not self.aliases else f"{self.name} {self.aliases}"
        return embed

    def get_user_storage(self, author):
        assert self.enable_usermap

        try:
            return self.usermap[author.id]
        except KeyError:
            self.usermap[author.id] = list()
            return self.usermap[author.id]

    def get_guild_settings_manager(self):
        return self.bot.guildsettings

    async def run(self, message, args, flags):
        raise NotImplementedError()

class CommandAlias:
    def __init__(self, origin):
        self.origin = origin

class GuildSettingsManager:
    def __init__(self, bot, defaultvalues={}):
        self.bot = bot
        self.defaultvalues = defaultvalues
        self.guildmap = {}

    async def get_database_connection(self):
        return await self.bot.get_database_connection()

    async def initialize_guild_variables(self, guildid):
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

    async def get_guild_variable(self, guildid, key, default=None):
        await self.initialize_guild_variables(guildid)
        
        return self.guildmap[guildid].get(key, default)

    async def get_guild_variables(self, guildid):
        await self.initialize_guild_variables(guildid)
        
        return self.guildmap[guildid]

    async def update_guild_variable(self, variable):
        dal = GuildVariableDAL(await self.get_database_connection())

        ok = await dal.update_variable(variable)

        if not ok:
            # Não existe ainda, crie
            return await dal.create_variable(variable)
        else:
            return ok

    async def remove_guild_variable(self, variable):
        # Isso vai voltar para o valor padrão
        dal = GuildVariableDAL(await self.get_database_connection())

        if await dal.remove_variable(variable):
            variable.set_value(self.defaultvalues[variable.key])

            return True

        return False

class Client(discord.Client):
    def __init__(self):
        super().__init__()
        
        self.listeners = {}

    async def on_message(self, message):
        await self.dispatch_event('message', message=message)

    async def on_ready(self):
        await self.dispatch_event('ready')

    async def on_reaction_add(self, reaction, user):
        await self.dispatch_event('reaction_add', reaction=reaction, user=user)

    def listen(self, token):
        self.run(token)

    def register_event(self, eventname, coroutinefunc, name=None):
        assert asyncio.iscoroutinefunction(coroutinefunc)

        eid = coroutinefunc.__name__ if name is None else name

        if not eventname in self.listeners:
            self.listeners[eventname] = dict()

        self.listeners[eventname][eid] = coroutinefunc
        
        return eid

    def remove_event(self, eventname, eid):
        del self.listeners[eventname][eid]

    async def dispatch_event(self, eventname, **kwargs):
        if not eventname in self.listeners:
            return

        for eid, coroutine in self.listeners[eventname].items():
            await coroutine(kwargs)

class Config:
    def __init__(self, configfile):
        self.kvalues = {}
        self.path = configfile

    def load(self):
        with open(self.path, 'r', encoding='utf-8') as f:
            self.kvalues = json.loads(''.join(f.readlines()))

    def get(self, keystr, default=None):
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
    def __init__(self, path=None, logfile=None, loglevel=logging.DEBUG):
        logging.basicConfig(
            filename=logfile, 
            format="[%(asctime)s] <%(levelname)s> %(message)s", 
            datefmt="%d/%m/%Y %H:%M:%S", 
            level=loglevel
        )

        self.curr_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if not path else path
        self.playing_interval = None

        self.config = Config(
            f'{self.curr_path}/release/config.json'
        )

        self.config.load()
        
        self.client = Client()
        self.client.register_event('message', self.receive_message)
        self.client.register_event('ready', self.receive_ready)

        self.commands = {}
        self.load_modules(f'{self.curr_path}/modules')
        
        self.active_database = None

        self.guildsettings = GuildSettingsManager(self, defaultvalues=self.config.get('guild_settings'))

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
                raise BotError('Não foi possível conectar-se à base de dados.')
        
        return self.active_database

    def load_modules(self, dirpath):
        with os.scandir(dirpath) as iterator:
            for file in iterator:
                if file.name.endswith('.py') and file.is_file():
                    mod = importlib.import_module(f"{dirpath[len(os.path.dirname(dirpath)) + 1:].replace('/', '.')}.{file.name[:-3]}")
                    self.load_commands_from_module(mod)

    def load_commands_from_module(self, mod):
        logging.info(f"Attempting to load commands from module: {mod}")
        
        for obj in inspect.getmembers(mod, lambda x: inspect.isclass(x) and is_subclass(x, BotCommand) and x != BotCommand):
            cmd = obj[1](self)

            assert inspect.iscoroutinefunction(getattr(cmd, 'run'))

            self.commands[cmd.name.lower()] = cmd

            for alias in cmd.aliases:
                self.commands[alias.lower()] = CommandAlias(cmd)

            logging.info(f"Successfully loaded a new command: {cmd.name} ({mod.__name__}.{type(cmd).__name__})")

    def listen(self):
        self.client.listen(self.config.get('global.token'))

    def create_response_embed(self, message, description=""):
        return discord.Embed(description=description, color=discord.Color.magenta()).set_footer(
            text=message.author.name, 
            icon_url=message.author.avatar_url_as(size=32)
        )

    async def set_playing_game(self, playingstr, status=None, afk=False):
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
        message = kwargs.get('message', None)

        if message.author == self.client.user or message.author.bot or not isinstance(message.channel, discord.TextChannel):
            return

        prefix = self.config.get('global.prefix', ';;')

        if not message.content.startswith(prefix):
            return
        
        parser = CommandParser(message.content[len(prefix):])

        try:
            pipeline = parser.parse()
            output = await self.handle_pipeline_execution(message, pipeline)

            if output:
                if isinstance(output, str):
                    await message.channel.send(embed=self.create_response_embed(message, description=output))
                elif isinstance(output, discord.Embed):
                    await message.channel.send(embed=output)
                elif isinstance(output, Slider):
                    await output.send()
                elif isinstance(output, CommandError):
                    await message.channel.send(embed=self.create_response_embed(message, f":warning: {output}"))
                else:
                    logging.error(f'Pipeline output is invalid: {output}')
        except (ParserError, PermissionLevelError, BotError) as e:
            await message.channel.send(embed=self.create_response_embed(message, f":red_circle: **{type(e).__name__}** : {e}"))

    async def has_permission_level(self, command, channel, author):
        if command.permissionlevel is PermissionLevel.NONE:
            return True
        elif command.permissionlevel is PermissionLevel.BOT_OWNER:
            return author.id in self.config.get('global.owner_ids', [])
        else:
            currlevel = None
            
            if isinstance(channel, discord.TextChannel):
                permissions = channel.permissions_for(author)

                if permissions.kick_members or permissions.ban_members:
                    currlevel = PermissionLevel.GUILD_MOD
                
                if permissions.administrator:
                    currlevel = PermissionLevel.GUILD_ADMIN

                if channel.guild.owner == author:
                    currlevel = PermissionLevel.GUILD_OWNER
            
            return currlevel.value >= command.permissionlevel.value if currlevel else False

    async def handle_pipeline_execution(self, message, pipeline):
        pipeline_output = ''
        
        for command in pipeline:
            handler = self.commands.get(command.cmd.lower(), None)

            if handler:
                handler = handler.origin if isinstance(handler, CommandAlias) else handler

                if not await self.has_permission_level(handler, message.channel, message.author):
                    raise PermissionLevelError(f"Você não possui um nível de permissão igual ou superior à `{handler.permissionlevel.name}`")

                args = command.args
                flags = command.flags

                for c in range(len(args)):
                    arg = args[c]
                    # É uma string literal, veja se precisa processar algum comando antes.
                    if isinstance(arg, list):
                        for i in range(len(arg)):
                            chunk = arg[i]
                            # Temos uma outra PIPELINE, execute ela recursivamente antes para termos o resultado.
                            if isinstance(chunk, list):
                                arg[i] = await self.handle_pipeline_execution(message, chunk)

                                if not isinstance(arg[i], str):
                                    raise BotError(f"O comando `{chunk[0].cmd}` não retornou dados compatíveis para utilizar de argumento...")

                        args[c] = ''.join(arg)

                if not isinstance(pipeline_output, str):
                    raise BotError(f"O comando `{command.cmd}` recebeu uma saída inválida, abortando...")
                
                pipeline_output = await self.handle_command_execution(handler, message, args, flags, received_pipe_data=pipeline_output)
            else:
                raise BotError(f"O comando `{command.cmd}` não existe, abortando...")

        return pipeline_output

    async def handle_command_execution(self, command, message, args, flags, received_pipe_data=''):
        # @TODO: Adicionar verificador de menções, pois o registro de menções é feito sobre todas as menções na mensagem completa,
        # porém, cada comando deveria somente ter acesso a lista de menções que lhe foi passada
        # Ex: "";;echo @Piratex "{av @Navi --url --size=32}"
        # o exemplo acima fará com que o comando avatar imprima o URL do avatar de @Piratex e não de @Navi
        
        assert is_instance(command, BotCommand)
        
        logging.info(f'Handling execution of {command.name}: {command}')
        output = None

        if 'h' in flags or 'help' in flags:
            output = command.get_usage_embed(message)
        else:
            try:
                if received_pipe_data:
                    args.append(received_pipe_data)

                output = await command.run(message, args, flags)
            except CommandError as e:
                logging.warn(f'Command {command.name} threw an error: {e}')
                output = e
            except Exception as e:
                logging.error(f'Uncaught exception thrown while running {command.name}: {e}\n\n{traceback.format_exc()}')

        return output

    async def callable_update_playing(self, intervalcontext, kwargs):
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

class TimeoutContext:
    def __init__(self, waitfor, callable, callback=None, **kwargs):
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
    def __init__(self, waitfor, callable, max_count=0, callback=None, ignore_exception=False, **kwargs):
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

class Slider:
    def __init__(self, client, message, items, reaction_right=r'▶️', reaction_left=r'◀️', restricted=False, startat=0, timeout=60):
        self.client = client
        self.message = message
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
        reaction = kwargs.get('reaction', None)
        user = kwargs.get('user', None)

        assert self.sent_message is not None
        assert reaction
        assert user
        assert type(self.registered_event_id) is not None

        if reaction.message.id != self.sent_message.id or user == self.client.user or (self.restricted and user != self.message.author):
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
                self.client.remove_event("reaction_add", self.registered_event_id)
            else:
                self.last_activity = time.time()

    async def send(self):
        assert self.items

        curritem = self.get_current_item()

        try:
            self.sent_message = await self.message.channel.send(embed=curritem)
        except (discord.Forbidden, discord.HTTPException) as e:
            self.caught_exception = e

        if not self.caught_exception:
            if len(self.items) == 1:
                return
            else:
                self.registered_event_id = self.client.register_event('reaction_add', self.callable_on_add_reaction, name=f'slider_send_{self.sent_message.id}')

            await asyncio.gather(
                self.sent_message.add_reaction(self.reaction_left),
                self.sent_message.add_reaction(self.reaction_right)
            )

            self.last_activity = time.time()
            while time.time() - self.last_activity <= self.timeout:
                await asyncio.sleep(self.timeout)

            if not self.caught_exception:
                self.client.remove_event("reaction_add", self.registered_event_id)