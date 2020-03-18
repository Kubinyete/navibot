import discord
import asyncio
import logging
import json
import os
import importlib
import inspect
import time
import naviutil
import traceback
from enum import Enum, auto

class CommandError(Exception):
    pass

class PipeError(Exception):
    pass

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
                self.client.remove_event('reaction_add')
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

class Command:
    def __init__(self, bot):
        self.bot = bot
        self.name = None
        self.description = None
        self.usage = None

    def initialize(self):
        raise NotImplementedError()

    async def run(self, args, flags):
        raise NotImplementedError()

class BotCommand(Command):
    def __init__(self, bot):
        super().__init__(bot)
        
        self.name = type(self).__name__.lower()
        self.aliases = []
        self.description = 'Descrição não disponível.'
        self.usage = None
        self.enable_usermap = False

        self.initialize()
        
        if not self.usage:
            self.usage = f"{self.name}"

        if self.enable_usermap:
            self.usermap = {}

    def create_response_embed(self, message, description=''):
        return self.bot.create_response_embed(message, description)

    def get_usage_embed(self, message):
        text = f"{self.description}\n\n`{self.usage}`"
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

    def initialize(self):
        pass

    async def run(self, message, args, flags):
        raise NotImplementedError()

class CommandAlias:
    def __init__(self, origin):
        self.origin = origin

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
            #logging.info(f"Dispatching event {eventname}, awaiting listener {eid} ({coroutine.__name__})")
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
    def __init__(self, configfile, logfile=None, loglevel=logging.DEBUG):
        logging.basicConfig(
            filename=logfile, 
            format="[%(asctime)s] <%(levelname)s> %(message)s", 
            datefmt="%d/%m/%Y %H:%M:%S", 
            level=loglevel
        )

        self.curr_path = os.path.dirname(os.path.abspath(__file__))
        self.playing_interval = None

        self.config = Config(configfile)
        self.config.load()
        
        self.client = Client()
        self.client.register_event('message', self.receive_message)
        self.client.register_event('ready', self.receive_ready)

        self.commands = {}
        self.load_modules(f'{self.curr_path}/modules')

    def load_modules(self, dirpath):
        with os.scandir(dirpath) as iterator:
            for file in iterator:
                if file.name.endswith('.py') and file.is_file():
                    mod = importlib.import_module(f"{dirpath[len(os.path.dirname(dirpath)) + 1:].replace('/', '.')}.{file.name[:-3]}")
                    self.load_commands_from_module(mod)

    def load_commands_from_module(self, mod):
        logging.info(f"Attempting to load commands from module: {mod}")
        
        for obj in inspect.getmembers(mod, lambda x: inspect.isclass(x) and naviutil.is_subclass(x, BotCommand)):
            cmd = obj[1](self)

            assert inspect.iscoroutinefunction(getattr(cmd, 'run'))

            self.commands[cmd.name] = cmd

            for alias in cmd.aliases:
                self.commands[alias] = CommandAlias(cmd)

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
                self.callable_update_playing
            )

            self.playing_interval.create_task()

    async def receive_message(self, kwargs):
        message = kwargs.get('message', None)

        if message.author == self.client.user or message.author.bot:
            return

        prefix = self.config.get('global.prefix', ';;')

        if not message.content.startswith(prefix):
            return
        
        try:
            commands = naviutil.parse_command_string(message.content[len(prefix):])
        
            processing_output = None
            i = 0
            for command in commands:
                i += 1

                handler = self.commands.get(command['command'], None)

                if handler:
                    args = command['args']
                    flags = command['flags']

                    processing_output = await self.handle_command_execution(handler, message, args, flags, received_pipe_data=processing_output, last_in_pipestream=i == len(commands))
                else:
                    raise ValueError(f"O comando `{command['command']}` não existe, abortando...")
        except (ValueError, PipeError) as e:
            await message.channel.send(embed=self.create_response_embed(message, f":red_circle: {e}"))

    async def handle_command_execution(self, command, message, args, flags, received_pipe_data=None, last_in_pipestream=False):
        output = None
        command = command.origin if isinstance(command, CommandAlias) else command

        logging.info(f'Handling execution of {command.name}: {command}')
        
        assert naviutil.is_instance(command, BotCommand)

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

        if output:
            if isinstance(output, str):
                if last_in_pipestream:
                    await message.channel.send(embed=self.create_response_embed(message, description=output))
                else:
                    return output
            elif isinstance(output, discord.Embed):
                await message.channel.send(embed=output)
            elif isinstance(output, Slider):
                await output.send()
            elif isinstance(output, CommandError):
                await message.channel.send(embed=self.create_response_embed(message, f":red_circle: {output}"))
            else:
                logging.error(f'Command {command.name} output is invalid: {output}')

        if not last_in_pipestream and not isinstance(output, str):
            raise PipeError(f"Abortando saída através do PIPE, o retorno do comando `{command.name}` não pode ser passado adiante.")

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
