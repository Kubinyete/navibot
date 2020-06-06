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
import re
import sys
import io
import aiohttp
import aiomysql
import PIL.Image

from enum import Enum, auto

from navibot.helpers import IntervalContext
from navibot.parser import CommandParser
from navibot.util import is_instance, is_subclass, bytes_string
from navibot.errors import *
from navibot.database.dal import GuildVariableDAL
from navibot.database.models import GuildVariable

class IBotNotifiable:
    async def receive_bot_start(self):
        raise NotImplementedError()

    async def receive_bot_reload(self):
        raise NotImplementedError()

    async def receive_bot_late_reload(self):
        raise NotImplementedError()

    async def receive_bot_shutdown(self):
        raise NotImplementedError()

    async def receive_bot_ready(self):
        raise NotImplementedError()

class PermissionLevel(Enum):
    NONE                = auto()
    GUILD_MOD           = auto()
    GUILD_ADMIN         = auto()
    GUILD_OWNER         = auto()
    BOT_OWNER           = auto()

class EmojiType(Enum):
    INFORMATION         = 'ℹ️'
    CHECK_MARK          = '✅'
    CROSS_MARK          = '❌'
    WARNING             = '⚠️'
    RED_HEART           = '❤️'
    THUMBS_UP           = '👍'
    THUMBS_DOWN         = '👎'
    THINKING            = '🤔'
    OK_HAND             = '👌'
    ARROW_FOWARD        = '▶️'
    ARROW_BACKWARD      = '◀️'
    ARROW_UPWARD        = '🔼'
    ARROW_DOWNWARD      = '🔽'

class ClientEvent(Enum):
    READY               = 'ready'
    MESSAGE             = 'message'
    MEMBER_JOIN         = 'member_join'
    REACTION_ADD        = 'reaction_add'
    REACTION_REMOVE     = 'reaction_remove'

class Context:
    def __init__(self, bot):
        self.bot = bot

    async def reply(self, response):
        raise NotImplementedError()

class BotContext(Context):
    def __init__(self, bot, channel: discord.TextChannel=None, author: discord.User=None, message: discord.Message=None):
        super().__init__(bot)
        self.channel = channel
        self.author = author
        self.message = message

    def create_response_embed(self):
        e = discord.Embed( 
            color=discord.Color.magenta()
        )

        if self.author:
            e.set_footer(
                text=self.author.name, 
                icon_url=self.author.avatar_url_as(size=32)
            )

        return e

    async def get_last_sent_attachment(self, limit: int, expected_file_extensions: tuple):
        if not self.channel or not self.message:
            raise BotError('É preciso que o contexto possua um canal e uma mensagem para poder obter um anexo.')

        async for message in self.channel.history(limit=limit, before=self.message.created_at):
            for atch in message.attachments:
                valid = False
                for ext in expected_file_extensions:
                    if atch.filename.lower().endswith('.' + ext):
                        valid = True
                        break

                if not valid:
                    continue
                else:
                    return atch

    # @NOTE:
    # Atualmente, nós esperamos sempre que um comando volte uma reply, mas nunca uma combinação, Ex: Attachment +
    # Texto de mensagem. Ou seja, se um comando for enviar duas coisas, terá que ser duas chamadas para reply()
    # separadas.
    async def reply(self, response, use_embed_as_default: bool=True):
        if not self.channel and not self.author:
            raise BotError('Não é possível responder o contexto atual, não existe nenhum canal ou usuário selecionado.')

        target = self.author if not self.channel else self.channel

        if isinstance(response, str) or isinstance(response, list):
            text = ' '.join(response) if isinstance(response, list) else response
            
            if use_embed_as_default:
                embed = self.create_response_embed()
                embed.description = text
                return await target.send(embed=embed)
            else:
                return await target.send(text)

        elif isinstance(response, discord.Embed):
            return await target.send(embed=response)

        elif isinstance(response, discord.File):
            return await target.send(file=response)

        elif isinstance(response, Slider):
            return await response.send()

        elif isinstance(response, EmojiType):
            if not self.message:
                raise BotError('É preciso vincular uma mensagem a este contexto para poder adicionar uma reação.')

            return await self.message.add_reaction(response.value)

        elif isinstance(response, Exception):
            embed = self.create_response_embed()
            embed.description = f'{EmojiType.CROSS_MARK.value} **{type(response).__name__}**: {response}'
            return await target.send(embed=embed)
        else:
            raise BotError('Não é possível responder a este contexto, pois o parâmetro informado não é de um tipo conhecido.')

class CliContext(Context):
    def __init__(self, bot, input_data: str, output_data: io.StringIO, botcontext: BotContext=None):
        super().__init__(bot)
        self.input_data = input_data
        self.output_data = output_data
        self.botcontext = botcontext

    def extract_output_data(self):
        data = self.output_data.getvalue()
        self.output_data.seek(0)
        self.output_data.truncate(0)
        return data

    # @TODO: 
    # Mover essa lógica para dentro de BotContext?, o uso disto aqui deveria ser
    # CliContext.botcontext.update_target()
    # mas isso aqui também faz sentido, nada grave
    def update_botcontext_target(self, target):
        if not isinstance(target, discord.User) and not isinstance(target, discord.TextChannel):
            raise BotError('É preciso selecionar como alvo um discord.User ou um discord.TextChannel.')

        if isinstance(target, discord.User):
            self.botcontext.author = target
            self.botcontext.channel = None
        else:
            self.botcontext.author = None
            self.botcontext.channel = target

    def format_response(self, response):
        if isinstance(response, str) or isinstance(response, list):
            response_data = '\n'.join(response) if isinstance(response, list) else response
        elif isinstance(response, discord.Embed):
            response_data = response.description
        elif isinstance(response, EmojiType):
            response_data = response.name
        elif isinstance(response, Exception):
            response_data = f'{type(response).__name__}: {response}'
        else:
            raise BotError('Não é possível responder a este contexto, pois o parâmetro informado não é de um tipo conhecido.')

        return response_data

    async def reply(self, response):
        response_data = self.format_response(response)

        if response_data:
            self.output_data.write(response_data)

    async def say(self, response, use_embed_as_default: bool=False):
        return await self.botcontext.reply(response, use_embed_as_default=use_embed_as_default)

class Command:
    def __init__(self, bot):
        self.bot = bot
        self.name = type(self).__name__.lower()
        self.description = 'Descrição não disponível.'
        self.usage = ''
        self.aliases = []
        self.supported_args_type = (str, )

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
            else:
                raise KeyError(f"O atributo {key} não pertence à um {type(self).__name__}.")

    async def run(self, ctx: Context, args: list, flags: dict):
        raise NotImplementedError()

    # @NOTE:
    # Wrapper para poder receber qualquer tipo de argumento e verificar
    # se o comando suporta aquele tipo de entrada.
    #
    # Isso foi adicionado para permitir por hora, que comandos possam ler por exemplo um Embed gerado por outro comando, até mesmo uma Exception pode ser passada
    # isso possibilitaria fazer algo do tipo:
    # ;if "expression" | then "commands" | catcherror "message"
    # Ex:
    # ;if "{time | substr 0 2} > 12" | then "say \"Agora já passou das 12:00 horas!\"" | else "say \"Não chegamos às 12:00 horas ainda!\""
    # Imagino que nesse exemplo, estamos passando algum tipo de estrutura que possibilite saber o contexto do comando anterior, algo do tipo abaixo ou algo semelhante mais elaborado
    # ConditionContext:
    #   self.codition_str = '12 > 12'
    #   self.result = True
    #
    # Podemos também passar arquivos inteiros em memória para outros comandos, evitando sobrecarga (efetuar download, passar para outro comando ja com o arquivo em memória)
    # ;triggered @prtx | thinking
    async def run_wrapper(self, ctx: Context, args, flags: dict):
        for arg in args:
            if not type(arg) in self.supported_args_type:
                raise CommandError(f'O comando `{self.name}` não recebeu um tipo de dados esperado como argumento...\n\nEsperado: `{self.supported_args_type}`\nObtido: `{type(arg)}`')

        return await self.run(
            ctx,
            args,
            flags
        )

class BotCommand(Command):
    # @NOTE:
    # Parar de usar enable_usermap pois para cada comando que usá-lo, temos um dicionário de usuários diferentes...
    # Pensar em uma outra forma de possuir uma "memória volátil" para os comandos usarem.
    def __init__(self, bot, permissionlevel: PermissionLevel=PermissionLevel.NONE, hidden: bool=False, enable_usermap: bool=False, **kwargs):
        super().__init__(bot)

        self.permissionlevel = permissionlevel
        self.hidden = hidden

        self.usermap = {} if enable_usermap else None

        self.update_info(kwargs)

    def get_usage_embed(self, ctx: BotContext):
        embed = ctx.create_response_embed()
        embed.description = self.get_usage_text()
        embed.title = f"{self.name}" if not self.aliases else f"{self.name} {self.aliases}"
        return embed

    def get_user_storage(self, author: discord.User):
        assert self.usermap is not None

        try:
            return self.usermap[author.id]
        except KeyError:
            self.usermap[author.id] = []
            return self.usermap[author.id]

    def get_prefered_image_size(self):
        return self.bot.config.get('modules.preferences.default_io_max_image_size', 256)

    def get_prefered_max_image_byte_size(self):
        return self.bot.config.get('modules.preferences.default_io_max_image_kb_size', 1024) * 1024

    def get_prefered_supported_image_formats(self):
        return self.bot.config.get('modules.preferences.default_io_supported_image_format', ('png', 'jpg', 'jpeg', 'gif', 'webp'))

    def get_prefered_output_image_format(self):
        return self.bot.config.get('modules.preferences.default_io_image_format', 'png')

    async def get_file_from_url(self, image_url: str, max_size: int=0):
        try:
            return await self.bot.http.get_file(image_url, max_size=max_size)
        except asyncio.TimeoutError:
            raise CommandError('Não foi possível obter a imagem através da URL fornecida, o tempo limite da requisição foi atingido.')
        except BotError as e:
            raise CommandError(f"Não foi possível obter a imagem através da URL fornecida, {e}.")

    async def get_image_object_from_bytes(self, image_bytes: io.BytesIO):
        supported_image_formats = self.get_prefered_supported_image_formats()

        def callable_image_format_is_valid():
            nonlocal image_bytes
            
            try:
                curr_img = PIL.Image.open(image_bytes)
                curr_img.load()
            except Exception:
                raise CommandError('Não foi possível abrir a imagem a partir dos dados recebidos.')

            if not curr_img.format or not curr_img.format.lower() in supported_image_formats:
                raise CommandError(f'O formato da imagem é inválido, este comando só aceita imagens no(s) formato(s): {supported_image_formats}.')
            else:
                return curr_img

        return await asyncio.get_running_loop().run_in_executor(
            None,
            callable_image_format_is_valid
        )

    async def get_image_target(self, ctx, args, flags, from_mention: bool=True, from_arg: bool=True, from_pipeline: bool=True, from_history: bool=True, from_author=False):
        mentions = flags.get('mentions', None)
        image_bytes = None
        image_url = None

        prefered_image_size = self.get_prefered_image_size()
        max_size = self.get_prefered_max_image_byte_size()
        supported_image_formats = self.get_prefered_supported_image_formats()

        if mentions:
            if not from_mention:
                return

            image_url = str(mentions[0].avatar_url_as(size=prefered_image_size))
        else:
            if args:
                # Tem um arquivo já nos argumentos (resultado de outro comando na pipeline)?
                image_url = [x for x in args if isinstance(x, discord.File)]
                
                if image_url:
                    if not from_pipeline:
                        return

                    image_bytes = image_url[0].fp
                    assert isinstance(image_bytes, io.BytesIO)
                else:
                    if not from_arg:
                        return

                    image_url = args[0]
            else:
                if from_author:
                    assert ctx.author
                    image_url = str(ctx.author.avatar_url_as(size=prefered_image_size))
                else:
                    if not from_pipeline:
                        return

                    history_max_depth = self.bot.config.get('modules.preferences.default_history_max_depth', 50)

                    atch = await ctx.get_last_sent_attachment(
                        history_max_depth, 
                        supported_image_formats
                    )

                    if atch:
                        if atch.size > max_size:
                            raise CommandError(f'O tamanho em bytes da ultima imagem neste canal ultrapassa o limite permitido de {bytes_string(max_size)} pelo comando.')
                        else:
                            image_url = atch.url
                    else:
                        raise CommandError(f'Não foi possível encontrar uma imagem suportada no histórico do canal nas últimas {history_max_depth} mensagens.')

        if not image_bytes:
            image_bytes = await self.get_file_from_url(image_url, max_size=max_size)

        return await self.get_image_object_from_bytes(image_bytes)

    async def run(self, ctx: BotContext, args: list, flags: dict):
        raise NotImplementedError()

class CliCommand(Command):
    def __init__(self, bot, **kwargs):
        super().__init__(bot)

        self.update_info(kwargs)

    def get_usage_text(self):
        return f"Uso: {self.name} {self.usage}\n\n{self.description}\n"

    async def run(self, ctx: CliContext, args: list, flags: dict):
        raise NotImplementedError()

class InterpretedCommand(BotCommand):
    def __init__(self, bot, command: str, **kwargs):
        super().__init__(bot, **kwargs)

        self.command = command

    async def run_command(self, command: str, ctx: BotContext, args: list, flags: dict):
        pipeline = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: CommandParser(command).parse()
        ) 
        
        # @NOTE:
        # Executa uma PIPELINE para executar este comando interpretado,
        # os parâmetros activator_args e activator_flags são preservados pois
        # apontam para os args e flags originais recebidos pelo comando interpretado.
        return await self.bot.handle_pipeline_execution(
            self.bot.commands,
            ctx,
            pipeline,
            activator_args=args,
            activator_flags=flags
        )

    async def run(self, ctx: BotContext, args: list, flags: dict):
        return await self.run_command(
            self.command,
            ctx,
            args,
            flags
        )

# @NOTE:
# Só para distinguir uma comando de um apelido, seria possível ter feito apenas
# commands['apelido'] = Command()
# Mas com isso não teriamos como saber se o comando que acessamos Command(), é o original ou não.
#
# Fica a ser visto isso aqui, mas não tem nada demais em fazer desta forma.
class CommandAlias:
    def __init__(self, origin: Command):
        self.origin = origin

class Plugin(IBotNotifiable):
    def __init__(self, bot):
        self.bot = bot
        # @NOTE:
        # Precisamos saber em memória, quais eventos esse Plugin registrou, pois em sua destruição, todos esses eventos devem ser 
        # retirados
        self.requested_events = []

    # @NOTE: 
    # É executado toda vez que um plugin está completamente carregado.
    async def on_plugin_load(self):
        pass

    # @NOTE: 
    # É executado toda vez que um plugin está para ser retirado do PluginsManager.
    async def on_plugin_destroy(self):
        pass

    # @NOTE: 
    # Só é executado uma vez quando estamos prestes a logar com o bot (apenas no primeiro Login).
    # Útil para Plugins que não vão sair em Runtime e portanto, podems carregar seu estado interno antes do client logar.
    async def on_bot_start(self):
        pass

    # @NOTE: 
    # É executado toda vez que um reload está para acontecer, mas ainda não ocorreu
    async def on_bot_reload(self):
        pass

    # @NOTE: 
    # É executado toda vez que um reload aconteceu, caso esse Plugin não tenha saido do PluginsManager, ele pode ser avisado através
    # deste evento para poder bindar eventos novamente e carregar seu estado.
    async def on_bot_late_reload(self):
        pass

    # @NOTE: 
    # É executado toda vez que um shutdown está para ocorrer
    async def on_bot_shutdown(self):
        pass

    # @NOTE: 
    # É executado toda vez que o client receber um on_ready, lembrando que isso é executado mais de uma vez de acordo com a discord.py
    async def on_bot_ready(self):
        pass

    def bind_event(self, eventname: ClientEvent, coroutinefunc: callable):
        self.requested_events.append((eventname, self.bot.client.register_event(eventname, coroutinefunc)))

    def clear_events(self):
        for event, coroutinefunc in self.requested_events:
            self.bot.client.remove_event(event,coroutinefunc)

    async def load(self):
        await self.on_plugin_load()

    async def destroy(self):
        await self.on_plugin_destroy()
        self.clear_events()
    
    # IBotNotifiable

    async def receive_bot_start(self):
        await self.on_bot_start()

    async def receive_bot_reload(self):
        await self.on_bot_reload()

    async def receive_bot_late_reload(self):
        await self.on_bot_reload()

    async def receive_bot_shutdown(self):
        await self.on_bot_shutdown()

    async def receive_bot_ready(self):
        await self.on_bot_ready()

class Client(discord.Client):
    def __init__(self):
        super().__init__()
        
        # Eventos globais, sempre ativados antes dos associados
        self.listeners = {}
        # Eventos associados à uma identificação
        self.assoc_listeners = {}

        self.assoc_allowed_events = (
            # Pode ser associado a uma Guild ID
            ClientEvent.MEMBER_JOIN, 
            # Pode ser associado a um Message ID
            ClientEvent.REACTION_ADD, 
            # Pode ser associado a um Message ID
            ClientEvent.REACTION_REMOVE
        )

    async def on_message(self, message: discord.Message):
        await self.dispatch_event(
            ClientEvent.MESSAGE, 
            message=message
        )

    async def on_ready(self):
        await self.dispatch_event(
            ClientEvent.READY
        )

    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        await asyncio.gather(
            self.dispatch_event(
                ClientEvent.REACTION_ADD, 
                reaction=reaction, 
                user=user
            ),
            self.dispatch_assoc_event(
                ClientEvent.REACTION_ADD,
                str(reaction.message.id),
                reaction=reaction, 
                user=user
            )
        )

    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        await asyncio.gather(
            self.dispatch_event(
                ClientEvent.REACTION_REMOVE, 
                reaction=reaction, 
                user=user
            ),
            self.dispatch_assoc_event(
                ClientEvent.REACTION_REMOVE, 
                str(reaction.message.id),
                reaction=reaction, 
                user=user
            )
        )

    async def on_member_join(self, member: discord.Member):
        await asyncio.gather(
            self.dispatch_event(
                ClientEvent.MEMBER_JOIN, 
                member=member
            ),
            self.dispatch_assoc_event(
                ClientEvent.MEMBER_JOIN, 
                str(member.guild.id),
                member=member
            )
        )

    def register_event(self, eventname: ClientEvent, coroutinefunc: callable):
        assert asyncio.iscoroutinefunction(coroutinefunc)

        if not eventname.value in self.listeners:
            self.listeners[eventname.value] = set()

        if not coroutinefunc in self.listeners[eventname.value]:
            self.listeners[eventname.value].add(coroutinefunc)
        else:
            raise KeyError(f'A callback {coroutinefunc.__name__} já está atribuida ao evento {eventname.name}.')
        
        return coroutinefunc

    def register_assoc_event(self, eventname: ClientEvent, coroutinefunc: callable, identity: str):
        assert eventname in self.assoc_allowed_events
        assert asyncio.iscoroutinefunction(coroutinefunc)
        assert identity

        if not eventname.value in self.assoc_listeners:
            self.assoc_listeners[eventname.value] = {}

        assoc = self.assoc_listeners[eventname.value]

        if not identity in assoc:
            assoc[identity] = set()

        assoc[identity].add(coroutinefunc)
                
        return identity

    def remove_event(self, eventname: ClientEvent, coroutinefunc: callable):
        self.listeners[eventname.value].remove(coroutinefunc)
        
        if not self.listeners[eventname.value]:
            del self.listeners[eventname.value]

    def remove_assoc_event(self, eventname: ClientEvent, identity: str, coroutinefunc: callable=None):
        if coroutinefunc:
            self.assoc_listeners[eventname.value][identity].remove(coroutinefunc)
        else:
            del self.assoc_listeners[eventname.value][identity]

        if not self.assoc_listeners[eventname.value]:
            del self.assoc_listeners[eventname.value]

    async def dispatch_event(self, eventname: ClientEvent, **kwargs):
        try:
            for coroutine in self.listeners[eventname.value]:
                asyncio.create_task(
                    coroutine(kwargs)
                )
        except KeyError:
            pass

    async def dispatch_assoc_event(self, eventname: ClientEvent, identity: str, **kwargs):
        try:
            for coroutine in self.assoc_listeners[eventname.value][identity]:
                asyncio.create_task(
                    coroutine(kwargs)
                )
        except KeyError:
            pass

class Config:
    def __init__(self, configfile: str):
        self.kvalues = {}
        self.path = configfile
        # Já tenta abrir o arquivo no construtor, pois já aconteceu de esquecermos o Config.load() posteriormente, após instanciar o objeto.
        self.load()

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

    # @TODO:
    # def set(): ?
    # Pois com isso podemos mudar parâmetros do bot durante Runtime

class CommandDictionary:
    def __init__(self):
        self.commands = {}

    def register_command(self, cmd):
        assert is_instance(cmd, Command)
        assert inspect.iscoroutinefunction(getattr(cmd, 'run'))
                
        self.commands[cmd.name.lower()] = cmd

        for alias in cmd.aliases:
            self.commands[alias.lower()] = CommandAlias(cmd)

    def unregister_command(self, cmd):
        assert is_instance(cmd, Command)

        del self.commands[cmd.name]

        for alias in cmd.aliases:
            if self.commands[alias] is cmd:
                del self.commands[alias]

    def get_command_by_name(self, name: str):
        try:
            target = self.commands[name.lower()]
            return target if not isinstance(target, CommandAlias) else target.origin
        except KeyError:
            return None

    def clear(self):
        self.commands.clear()

    def get_all_commands(self, show_hidden: bool=False):
        cmds = []
        
        for value in self.commands.values():
            # @NOTE:
            # Se for um apelido, não mostre.
            # Agora, se for um CliCommand, nem verifique se ele é hidden, pois não existe CliCommand hidden no nosso caso.
            # Agora se não for nenhum das verificações acima, verifique se hidden é False
            if not isinstance(value, CommandAlias) and (is_instance(value, CliCommand) or show_hidden or not value.hidden):
                cmds.append(value)

        return cmds

    # @NOTE:
    # Versão mais amigável de register_command()
    # Faz verificações se podemos atribuir em cima de outro InterpretedCommand
    def add_interpreted_command(self, command: InterpretedCommand):
        assert is_instance(command, InterpretedCommand)
        logging.info(f"Adding interpreted command: {command.name} ({command})")

        target = self.get_command_by_name(command.name)
        if target:
            if isinstance(target, InterpretedCommand):
                self.register_command(command)
            else:
                raise BotError(f'O comando {command.name} já existe e não pode ser substituido.')
        else:
            self.register_command(command)

    # @NOTE:
    # Versão mais amigável de unregister_command()
    def remove_interpreted_command(self, name: str):
        command = self.get_command_by_name(name)

        if command:
            if isinstance(command, InterpretedCommand):
                self.unregister_command(command)
                logging.info(f"Removing interpreted command: {command.name} ({command})")
            else:
                raise BotError(f'O comando {command.name} já existe e não pode ser substituido.')

            return command
        else:
            raise BotError(f'O comando {name} não existe.')

class PluginsManager(IBotNotifiable):
    def __init__(self):
        self.plugins = {}

    async def register_plugin(self, plugin):
        assert is_instance(plugin, Plugin)
        typep = type(plugin)

        if not typep in self.plugins:
            self.plugins[typep] = plugin
            await plugin.load()
        else:
            logging.info(f'O plugin {typep.__name__} ({plugin}) já está registrado, ignorando novo register_plugin')

    def get_plugin_by_type(self, plugintype):
        return self.plugins[plugintype]

    async def unregister_plugin(self, plugin):
        assert is_instance(plugin, Plugin)
        typep = type(plugin)

        await plugin.destroy()
        del self.plugins[typep]

    async def unregister_plugin_by_type(self, plugintype):
        if plugintype in self.plugins:
            await self.unregister_plugin(self.plugins[plugintype])
        else:
            logging.info(f'O plugin de tipo {plugintype.__name__} não foi encontrado.')

    async def unregister_all(self):
        coroutinelist = []
        for instance in self.plugins.values():
            # Nao podemos parar a cada destroy()
            # Agente todos de uma vez
            coroutinelist.append(self.unregister_plugin(instance))

        await asyncio.gather(*coroutinelist)

        # @TODO:
        # Podemos futuramente ter plugins que resistam à um reload
        assert not self.plugins

    # IBotNotifiable

    async def receive_bot_start(self):
        for instance in self.plugins.values():
            await instance.receive_bot_start()

    async def receive_bot_reload(self):
        for instance in self.plugins.values():
            await instance.receive_bot_reload()

    async def receive_bot_late_reload(self):
        for instance in self.plugins.values():
            await instance.receive_bot_late_reload()

    async def receive_bot_shutdown(self):
        for instance in self.plugins.values():
            await instance.receive_bot_shutdown()

    async def receive_bot_ready(self):
        for instance in self.plugins.values():
            await instance.receive_bot_ready()

class GuildSettingsManager:
    def __init__(self, bot, default_values: dict, cache_timelimit: int=60 * 30):
        self.bot = bot
        self.default_values = default_values
        self.guildmap = {}
        self.cache_timelimit = cache_timelimit

        # @NOTE:
        # Provavelmente uma das coisas mais legais que eu gostei de fazer,
        # isso permite que nós tenhamos um conceito de key, value dinâmico no banco
        # aonde cada Guid tem suas variáveis setadas de acordo com suas necessidades
        # o legal de não depender de uma definição de tabela, é que, após termos uma única tabela em
        # banco, podemos adicionar qualquer variável que precisarmos, sem precisar editar a estrutura da table.
        # o único downside, é que essa approach usando key, value em banco, através da conversão do valor em string
        # para um valor em memória é um processo mais lento, porém acredito que os benefícios neste caso fazem justiça (facilidade e dinamicidade).

    async def get_cacheable_guild_variable(self, guildid: int, key: str):
        async with (await self.bot.get_connection_pool()).acquire() as conn:
            dal = GuildVariableDAL(conn)

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
        async with (await self.bot.get_connection_pool()).acquire() as conn:
            dal = GuildVariableDAL(conn)

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
        async with (await self.bot.get_connection_pool()).acquire() as conn:
            dal = GuildVariableDAL(conn)

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
        async with (await self.bot.get_connection_pool()).acquire() as conn:
            dal = GuildVariableDAL(conn)

            ok = await dal.remove_variable(variable)

            if ok and variable.key in self.guildmap[variable.guildid]:
                del self.guildmap[variable.guildid][variable.key]

            return ok

class LocalizationManager:
    def __init__(self, guildsettings: GuildSettingsManager, configfile: str, default_lang: str='pt-BR'):
        self.guildsettings = guildsettings
        self.config = Config(configfile)
        self.default_lang = default_lang

    def load(self):
        return self.config.load()

    def translate(self, lang: str, tlkey: str):
        return self.config.get(f'{lang}.{tlkey}', f'{lang}.{tlkey}')

    async def translate_gc(self, guildid: int, tlkey: str):
        curr_lang = await self.guildsettings.get_guild_variable(guildid, 'bot_lang')

        if curr_lang:
            curr_lang = curr_lang.get_value()
            return self.translate(curr_lang, tlkey)
        else:
            return self.translate(self.default_lang, tlkey)

class HttpManager:
    def __init__(self, default_timeout: int=60):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(
                total=default_timeout
            )
        )

    async def get_file(self, url: str, max_size: int=0):
        out = io.BytesIO()

        async with self.session.get(url) as r:
            if r.status != 200:
                raise BotError(f'A requisição GET para {url} não retornou 200 OK.')

            if max_size > 0:
                assert 'CONTENT-LENGTH' in r.headers and int(r.headers.get('CONTENT-LENGTH')) <= max_size
            
            out.write(await r.read())

        out.seek(0, io.SEEK_SET)
        return out

    async def get_json(self, url: str):
        async with self.session.get(url) as r:
            return await r.json()

    async def close_session(self):
        return await self.session.close()

class Bot:
    def __init__(self, path: str=None, logenable: bool=True, logfile: str=None, loglevel=logging.DEBUG):
        # @NOTE:
        # Se não recebermos por parametro um caminho, tente nós mesmos descobrir isso
        self.curr_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if not path else path

        # Log básico, não queremos nada "fancy"
        if logenable:
            logging.basicConfig(
                filename=logfile, 
                format="[%(asctime)s] <%(levelname)s> %(message)s", 
                datefmt="%d/%m/%Y %H:%M:%S", 
                level=loglevel
            )

        # @NOTE:
        # Nosso objeto para carregar valores do arquivo de configurações
        # Prepara as Configs e o Client
        self.config = Config(f'{self.curr_path}/release/config.json')
        self.client = Client()

        # @NOTE: 
        # Componentes essenciais:
        # Dicionário de comandos, Plugins e nosso gerênciador de variáveis por Guild.
        self.commands = CommandDictionary()
        self.clicommands = CommandDictionary()
        self.plugins = PluginsManager()
        self.http = HttpManager(default_timeout=30)
        self.guildsettings = GuildSettingsManager(self, self.config.get('guild_settings'), cache_timelimit=60 * 30)
        self.lm = LocalizationManager(self.guildsettings, f'{self.curr_path}/localization.json', default_lang='pt-BR')

        # Objeto de conexão de banco de dados ativo no momento.
        self.connection_pool = None
        # Objeto de sessão ativa no momento.
        self.active_http_session = None
        # Event loop
        self.loop = None

    # @NOTE:
    # "Eventos" internos, facilita a leitura

    async def notify_internal_start(self):
        await self.plugins.receive_bot_start()

    async def notify_internal_reload(self):
        await self.plugins.receive_bot_reload()
    
    async def notify_internal_late_reload(self):
        await self.plugins.receive_bot_late_reload()

    async def notify_internal_shutdown(self):
        await self.plugins.receive_bot_shutdown()
        
        if self.active_http_session:
            await self.active_http_session.close()

    async def notify_internal_ready(self):
        await self.plugins.receive_bot_ready()

    # @NOTE:
    # Nosso ponto de entrada sync.
    def start(self):
        self.loop = asyncio.get_event_loop()

        try:
            self.loop.run_until_complete(self.astart())
        except KeyboardInterrupt:
            self.loop.run_until_complete(self.astop())
        finally:
            self.loop.close()

    async def astart(self):
        assert self.loop

        # Prepara já as callbacks nativas
        self.register_native_events()

        # Carrega todos os modulos, seus comandos e plugins
        await self.load_all_modules()
        
        # Notifica que um evento de início interno do bot está ocorrendo
        await self.notify_internal_start()

        # Efetua login pelo client
        await self.client.start(self.config.get('global.token'))

    async def astop(self):
        # Avisa todos os componentes que precisam ser notificados que o bot está desligando..
        await self.notify_internal_shutdown()
        # Logout no Client
        await self.client.logout()

    def register_native_events(self):
        # Diferente da implementação por Plugin
        # Esses registros não saem, são nativos
        self.client.register_event(ClientEvent.MESSAGE, self.callable_receive_message)
        self.client.register_event(ClientEvent.READY, self.callable_receive_ready)

    # @NOTE:
    # Isso é async pois precisamos notificar os plugins, cada um deles, e decidi que todos os eventos
    # seriam async, portanto, isso é uma chamada em cascata
    async def load_all_modules(self, is_reloading: bool=False):
        if is_reloading:
            # Precisamos avisar que os plugins sofrerão reload e outras coisas se necessário
            await self.notify_internal_reload()

            # Pode limpar de forma blocking
            self.commands.clear()
            
            # Limpa os plugins de uma só vez
            await self.plugins.unregister_all()

        # Popula o dicionário acima, procurando os modulos em NAVI_PATH/modules e encontra comandos e hooks
        await self.load_modules(f'{self.curr_path}/modules', force_reload=True)

        if is_reloading:
            # Precisamos avisar que os plugins deram reload
            await self.notify_internal_late_reload()

    # @NOTE:
    # Só é async devido ao load_all_modules() acima, pois na verdade não tem nada async aqui novamente
    async def load_modules(self, dirpath: str, force_reload: bool=False):
        with os.scandir(dirpath) as iterator:
            for file in iterator:
                if file.is_file() and file.name.endswith('.py'):
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
                        await self.load_objects_from_module(mod)

    # @NOTE:
    # async, mesma coisa que load_modules()
    async def load_objects_from_module(self, mod):
        logging.info(f"Attempting to load commands from module: {mod}")
        
        # Não gosto muito dessa lambda, mas pore enquanto vamos filtrar assim...
        for obj in inspect.getmembers(mod, lambda x: inspect.isclass(x) and (
                is_subclass(x, BotCommand) and x != BotCommand and x != InterpretedCommand 
                or 
                is_subclass(x, Plugin) and x != Plugin
                or
                is_subclass(x, CliCommand) and x != CliCommand
            )):
            cmd = obj[1](self)

            if is_instance(cmd, BotCommand):
                self.commands.register_command(cmd)
                logging.info(f"Successfully loaded a new Command: {cmd.name} ({mod.__name__}.{type(cmd).__name__})")
            elif is_instance(cmd, CliCommand):
                self.clicommands.register_command(cmd)
                logging.info(f"Successfully loaded a new CLI Command: {cmd.name} ({mod.__name__}.{type(cmd).__name__})")
            else:
                await self.plugins.register_plugin(cmd)
                logging.info(f"Successfully loaded a new Plugin: {mod.__name__}.{type(cmd).__name__} ({cmd})")

    # @NOTE:
    # É async, pois isso é chamado através dos comandos
    async def reload_all_modules(self):
        logging.info(f"Reloading configuration file and all modules...")
        
        # Carrega novamente as chaves
        self.config.load()

        await self.load_all_modules(True)

    # @NOTE: 
    # Cria a conexão de forma lazy.
    # 
    # Aqui podemos também executar coisas antes de tentar obter a conexão:
    # Ex: Verificar se está tudo OK, pois todo comando que usará um componente que acessa o banco eventualmente
    # vai chegar neste trecho de código.
    async def get_connection_pool(self):
        # Se não travarmos isso aqui, pode ser que aconteca 2 vezes ou mais o create_pool()
        async with asyncio.Lock():
            if not self.connection_pool:
                try:
                    self.connection_pool = await aiomysql.create_pool(
                        host=self.config.get('database.host', '127.0.0.1'),
                        port=self.config.get('database.port', 3306),
                        user=self.config.get('database.user', 'root'),
                        password=self.config.get('database.password', ''),
                        db=self.config.get('database.db', 'navibotdb')
                    )
                except Exception as e:
                    logging.error(f'Connecting to the database failed: {e}')
                    raise DatabaseError('Não foi possível conectar-se à base de dados.')
            
            return self.connection_pool

    def has_permission_level(self, permissionlevel: PermissionLevel, ctx: BotContext):
        return self.rate_author_permission_level(ctx).value >= permissionlevel.value

    def rate_author_permission_level(self, ctx: BotContext):
        assert ctx.author
        assert ctx.channel

        permlevel = PermissionLevel.NONE

        if ctx.author.id in self.config.get('global.owner_ids', []):
            permlevel =  PermissionLevel.BOT_OWNER
        else:
            permissions = ctx.channel.permissions_for(ctx.author)

            if permissions.kick_members or permissions.ban_members:
                permlevel = PermissionLevel.GUILD_MOD
            if permissions.administrator:
                permlevel = PermissionLevel.GUILD_ADMIN
            if ctx.channel.guild.owner == ctx.author:
                permlevel = PermissionLevel.GUILD_OWNER

        return permlevel

    def extract_mentions_from(self, args: list, flags: dict, ctx: BotContext):
        assert ctx.channel

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
                        found = ctx.channel.guild.get_role(num)
                    else:
                        # Usuario e Usuario (Apelido)
                        dest_list = flags['mentions']
                        found = ctx.channel.guild.get_member(num)
                elif arg[1] == '#':
                    dest_list = flags['channel_mentions']
                    found = ctx.channel.guild.get_channel(num)

                if found:
                    dest_list.append(found)
                else:
                    raise BotError(f'O objeto `{num}` mencionado não foi encontrado na Guild atual.')

    async def set_playing_game(self, playingstr: str, status=discord.Status, afk: bool=False):
        logging.info(f'set_playing_game Bot is about to change presence to {playingstr}')

        return await self.client.change_presence(
            activity=discord.Game(playingstr), 
            status=status, 
            afk=afk
        )

    async def get_bot_prefix(self, ctx: BotContext):
        assert ctx.channel

        var = None

        try:
            var = await self.guildsettings.get_guild_variable(ctx.channel.guild.id, 'bot_prefix')
        except DatabaseError:
            pass

        if var and var.get_value():
            return var.get_value()
            
        return self.config.get('global.prefix', ';')

    async def reset_bot_prefix(self, ctx: Context):
        assert ctx.channel

        if not self.has_permission_level(PermissionLevel.GUILD_MOD, ctx):
            raise PermissionLevelError(f'Você não possui um nível de permissão igual ou superior à `{PermissionLevel.GUILD_MOD.name}`  para poder realizar esta ação.')

        var = await self.guildsettings.get_guild_variable(ctx.channel.guild.id, 'bot_prefix')
        
        if var:
            return await self.guildsettings.remove_guild_variable(var)
        else:
            raise Exception(f'Variável `bot_prefix` não encontrado no contexto da Guild atual.')

    async def callable_receive_ready(self, kwargs):
        logging.info(f"Successfully logged in")

        await self.notify_internal_ready()

    async def callable_receive_message(self, kwargs):
        message = kwargs.get('message')

        # Somente aceita mensagens que não são do próprio bot, que não são de outros bots e que está vindo de um canal de texto de uma Guild.
        if message.author.bot or message.author == self.client.user or not isinstance(message.channel, discord.TextChannel):
            return

        # Contexto utilizado daqui em diante...
        ctx = BotContext(
            self,
            message.channel,
            message.author,
            message
        )

        prefix = await self.get_bot_prefix(ctx)

        if not ctx.message.content.startswith(prefix):
            if self.client.user in ctx.message.mentions:
                if 'resetprefix' in ctx.message.content:
                    try:
                        if await self.reset_bot_prefix(ctx):
                            await ctx.reply(EmojiType.CHECK_MARK)
                        else:
                            await ctx.reply(EmojiType.CROSS_MARK)
                    except PermissionLevelError as e:
                        await ctx.reply(e)
                    except Exception as e:
                        logging.exception(f'RECEIVE_MESSAGE: {type(e).__name__}: {e}')
                        await ctx.reply(EmojiType.CROSS_MARK)
                else:
                    await ctx.reply(f'Por acaso esqueceu o prefixo do bot para esta Guild?\n\nO prefixo atual está configurado para `{prefix}`\n\nPara voltar o prefixo ao padrão, mencione o bot novamente com a palavra `resetprefix`.')
            return
        else:
            resolve_subcommands = True
            if ctx.message.content.startswith(prefix + '!'):
                prefix += '!'
                resolve_subcommands = False
        
        await self.handle_command_parse(ctx, ctx.message.content[len(prefix):], resolve_subcommands)

    async def handle_cli_command_parse(self, ctx: CliContext, content: str):
        return await self.handle_command_parse(ctx, content, resolve_subcommands=False, alternative_target_commands=self.clicommands)

    async def handle_command_parse(self, ctx: Context, content: str, resolve_subcommands: bool=True, alternative_target_commands: CommandDictionary=None):
        try:
            pipeline = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: CommandParser(content, resolve_subcommands).parse()
            )

            output = await self.handle_pipeline_execution(
                self.commands if not alternative_target_commands else alternative_target_commands, 
                ctx, 
                pipeline
            )

            if output:
                await ctx.reply(output)
        except (ParserError, BotError, PermissionLevelError, CommandError, DatabaseError) as e:
            # Exception "amigável", envie isso no contexto atual de volta para o usuário
            await ctx.reply(e)

    async def handle_pipeline_execution(self, target_commands: CommandDictionary, ctx: Context, pipeline, activator_args: list=None, activator_flags: dict=None):
        pipeline_output = ''
        
        for command in pipeline:
            handler = target_commands.get_command_by_name(command.cmd)

            if handler:
                handler = handler.origin if isinstance(handler, CommandAlias) else handler

                if is_instance(handler, BotCommand) and not self.has_permission_level(handler.permissionlevel, ctx):
                    raise PermissionLevelError(f"Você não possui um nível de permissão igual ou superior à `{handler.permissionlevel.name}`")

                # @TODO:
                # Isso está muito difícil para ler e compreender
                # Tentar separar esse processo em outros pedaços
                #
                # @NOTE:
                # Isso faz o seguinte, dada uma estrutura de "PIPELINE" voltada por CommandParser.parse()
                # você vai fazendo a resolução de cada argumento que for outroa PIPELINE, tentando
                # resolver isso para uma string comum utilizada de argumento para o comando inferior.
                # Essa função também trata da passagem de um output para ser utilizado de input para
                # o próximo comando.

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
                                # @NOTE:
                                # A execução dessa PIPELINE é dentro de uma string, ou seja, PRECISA RETORNAR UMA LISTA DE STRINGS OU UMA STRING.
                                arg[i] = await self.handle_pipeline_execution(target_commands, ctx, chunk, activator_args=activator_args, activator_flags=activator_flags)

                                # Recebemos uma string ou lista de strings?
                                if not isinstance(arg[i], str) and not isinstance(arg[i], list):
                                    raise BotError(f"O comando `{chunk[0].cmd}` não retornou dados compatíveis para utilizar de argumento...")
                                elif isinstance(arg[i], list):
                                    # As listas precisam reduzidas em simples strings para poder continuarem como argumento deste comando.
                                    arg[i] = ' '.join(arg[i])

                        # Retorne todos os pedaços a um só argumento string único.
                        args[c] = ''.join(arg)
                
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
                # raise BotError(f"O comando `{command.cmd}` não existe, abortando...")
                logging.warn(f"O comando `{command.cmd}` não existe, abortando...")

        # Terminando todo o processamento desta PIPELINE, volte para cima.
        return pipeline_output

    async def handle_command_execution(self, command: Command, ctx: Context, args: list, flags: dict, received_pipe_data='', activator_args: list=None, activator_flags: dict=None):
        logging.info(f'Handling execution of {command.name}: {command}')

        output = None

        # Se estamos requisitando apenas ajuda.
        if 'h' in flags or 'help' in flags:
            # Se você sabe que é um comando do bot, volte em um "formato rico" (embed), se não, pegue por padrão apenas o valor "cru" (texto)
            output = command.get_usage_embed(ctx) if is_instance(command, BotCommand) else command.get_usage_text()
        else:
            # Precisamos definir quem são as menções recebidas por argumento (não posso depender de message.mentions, etc...)
            if is_instance(command, BotCommand):
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
                output = await command.run_wrapper(
                    ctx,
                    args, 
                    flags
                )
            except (CommandError, DatabaseError) as e:
                # Unica forma aceitável de Exception dentro de um comando.
                logging.warn(f'Command {command.name} threw an error: {e}')
                # Envia para cima, pois se ignorarmos isso não será mostrado para o usuário
                raise e
            except Exception as e:
                # Por padrão, não mostrar Exceptions vindo de comandos, deixar isso para o console.
                logging.exception(f'Uncaught exception thrown while running {command.name}: {e}\n\n{traceback.format_exc()}')

        return output

# @NOTE:
# Estruturas para os comandos utilizarem:

# @TODO:
# Reescrever isso aqui?
class Slider:
    def __init__(self, bot: Bot, ctx: BotContext, items: list, reaction_right: str=r'▶️', reaction_left: str=r'◀️', restricted: bool=False, startat: int=0, timeout: int=60):
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
        assert self.sent_message and self.registered_event_id

        reaction = kwargs['reaction']
        user = kwargs['user']

        if user == self.bot.client.user or (self.restricted and user != self.ctx.author):
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
                self.bot.client.remove_assoc_event(
                    ClientEvent.REACTION_ADD,
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
                self.registered_event_id = self.bot.client.register_assoc_event(
                    ClientEvent.REACTION_ADD, 
                    self.callable_on_add_reaction,
                    str(self.sent_message.id)
                )

            await asyncio.gather(
                self.sent_message.add_reaction(self.reaction_left),
                self.sent_message.add_reaction(self.reaction_right)
            )

            self.last_activity = time.time()
            while time.time() - self.last_activity <= self.timeout:
                await asyncio.sleep(self.timeout)

            if not self.caught_exception:
                self.bot.client.remove_assoc_event(
                    ClientEvent.REACTION_ADD,
                    self.registered_event_id
                )
