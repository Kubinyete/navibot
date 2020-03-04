# Modulo principal
import discord
import asyncio
import logging
import json
import os
import importlib
import inspect
import naviutil
from enum import Enum, auto

class Permission(Enum):
    BASIC = auto()
    MOD = auto()
    ADMIN = auto()
    OWNER = auto()

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

    @staticmethod
    def create_response_embed(message, description=''):
        return Bot.create_response_embed(message, description)

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

class CommandError(Exception):
    pass

class Client(discord.Client):
    def __init__(self):
        super().__init__()
        self.listeners = {}

    async def on_message(self, message):
        await self.dispatch_event('message', message=message)

    def listen(self, token):
        self.run(token)

    def register_event(self, eventname, coroutinefunc):
        if eventname in self.listeners:
            self.listeners[eventname].append(coroutinefunc)
        else:
            self.listeners[eventname] = list()
            self.listeners[eventname].append(coroutinefunc)

    async def dispatch_event(self, eventname, **kwargs):
        for coroutine in self.listeners[eventname]:
            if asyncio.iscoroutinefunction(coroutine):
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

        self.config = Config(configfile)
        self.config.load()
        
        self.client = Client()
        self.client.register_event('message', self.receive_message)

        self.commands = {}
        self.load_modules(f'{self.curr_path}/modules')

    def load_modules(self, dirpath):
        with os.scandir(dirpath) as iterator:
            for file in iterator:
                if file.name.endswith('.py') and file.is_file():
                    mod = importlib.import_module(f"{dirpath[len(os.path.dirname(dirpath)) + 1:].replace('/', '.')}.{file.name[:-3]}")
                    self.load_commands_from_module(mod)

    def load_commands_from_module(self, mod):
        logging.info(f"NAVIBOT > Attempting to load commands from module -> {mod}")
        
        for obj in inspect.getmembers(mod, lambda x: inspect.isclass(x) and naviutil.is_subclass(x, BotCommand)):
            cmd = obj[1](self)

            assert inspect.iscoroutinefunction(getattr(cmd, 'run'))

            self.commands[cmd.name] = cmd

            for alias in cmd.aliases:
                self.commands[alias] = CommandAlias(cmd)

            logging.info(f"NAVIBOT > Successfully loaded a new BotCommand -> {cmd.name} ({mod.__name__}.{type(cmd).__name__})")

    def listen(self):
        self.client.listen(self.config.get('global.token'))

    @staticmethod
    def create_response_embed(message, description=""):
        return discord.Embed(description=description).set_footer(
            text=message.author.name, 
            icon_url=message.author.avatar_url_as(size=32)
        )

    async def receive_message(self, kwargs):
        message = kwargs.get('message', None)

        if message.author == self.client.user or message.author.bot:
            return

        prefix = self.config.get('global.prefix', ';;')

        if not message.content.startswith(prefix):
            return
        
        args, flags = naviutil.parse_args(message.content[len(prefix):])
        
        if args:
            command = self.commands.get(args[0], None)
         
            if command:
                await self.handle_command_execution(command, message, args, flags)

    async def handle_command_execution(self, command, message, args, flags):
        output = None
        command = command.origin if isinstance(command, CommandAlias) else command

        logging.info(f'NAVIBOT > Handling execution of {command.name} = {command}')
        
        assert naviutil.is_instance(command, BotCommand)

        try:
            output = await command.run(message, args[1:], flags)
        except CommandError as e:
            logging.warn(f'NAVIBOT > Command {command.name} threw an error: {e}')
            output = e
        except Exception as e:
            logging.error(f'NAVIBOT > Uncaught exception thrown while running {command.name}: {e}')
        finally:
            if output:
                if isinstance(output, str):
                    await message.channel.send(output)
                elif isinstance(output, discord.Embed):
                    await message.channel.send(embed=output)
                elif isinstance(output, CommandError):
                    await message.channel.send(embed=self.create_response_embed(message, f"{output}"))
                else:
                    logging.error(f'NAVIBOT > Command {command.name} output is invalid: {output}')