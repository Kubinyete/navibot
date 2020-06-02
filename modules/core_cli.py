import asyncio
import logging
import discord
import json
import io
from navibot.client import CliCommand, BotContext, CliContext, ClientEvent, Plugin
from navibot.errors import CommandError

class PConnectionManager(Plugin):
    def __init__(self, bot):
        super().__init__(bot)
        
        self.manager = ConnectionManager(
            bot, 
            self.bot.config.get('connections.listen', '127.0.0.1'),
            self.bot.config.get('connections.port', 7777)
        )

    async def on_plugin_load(self):
        self.bind_event(
            ClientEvent.MESSAGE,
            self.callable_transmit_message
        )

        await self.manager.start_server()

    async def on_plugin_destroy(self):
        if self.manager.is_accepting_connections():
            await self.manager.stop_server()

    async def on_bot_start(self):
        logging.info(f'Bot is currently listening to connections on {self.manager.host}:{self.manager.port}!')

    async def on_bot_shutdown(self):
        if self.manager.is_accepting_connections():
            await self.manager.stop_server()

    async def callable_transmit_message(self, kwargs):
        message = kwargs.get('message')

        # Só aceita mensagens por privado ou de um canal de texto
        if isinstance(message.channel, discord.TextChannel) or isinstance(message.channel, discord.DMChannel):
            self.manager.transmit_message_to_all_active_connections(message)

class CliConnection:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, bot_context: BotContext):
        self.reader = reader
        self.writer = writer
        self.peername = writer.get_extra_info("peername")

        self.bot_context = bot_context

    async def read_data(self):
        if not self.writer.is_closing():
            return await self.reader.readline()

    async def write_packet(self, packet: dict):
        if not self.writer.is_closing():
            logging.info(f'write_packet: Sending packet {packet} to {self.peername}')

            self.writer.write(
                (json.dumps(packet) + '\n').encode('utf-8')
            )

            await self.writer.drain()

    async def wait_closed(self):
        await self.writer.wait_closed()

    def close(self):
        assert self.writer.can_write_eof()

        if not self.writer.is_closing():
            self.writer.write_eof()
            self.writer.close()

    def is_closing(self):
        return self.writer.is_closing()

    def at_eof(self):
        return self.reader.at_eof()

class ConnectionManager:
    def __init__(self, bot, listen: str, port: int):
        self.bot = bot
        self.host = listen
        self.port = port
        self.open_server = None

        self.handlers = {
            "command_request": self.handle_command_request
        }
        
        self.active_connections = []

    def is_accepting_connections(self):
        return self.open_server != None

    async def start_server(self):
        assert not self.is_accepting_connections()
        try:
            self.open_server = await asyncio.start_server(
                self.callable_receive_connection,
                self.host,
                self.port,
                start_serving=True
            )
        except Exception:
            logging.info(f'ConnectionManager could not start server, aborting...')
            return

    async def stop_server(self):
        assert self.is_accepting_connections()
        self.close_all_active_connections()
        self.open_server.close()
        await self.open_server.wait_closed()

    async def callable_receive_connection(self, reader, writer):
        peername = writer.get_extra_info("peername")
        logging.info(f'callable_receive_connection: Received new connection from {peername}')

        # Encapsule essa conexão em um objeto, para outros objetos (Plugin) tenham acesso por fora
        cliconn = CliConnection(
            reader,
            writer,
            # Contexto do bot para que seja possível entender se é possível mandar uma mensagem em um canal de texto ou DM, etc...
            # É persistente durante toda a conexão, só será removido da memória quando o cliente desconectar
            BotContext(
                self.bot
            )
        )

        self.active_connections.append(cliconn)

        data = await cliconn.read_data()
        while data and not (cliconn.at_eof() or cliconn.is_closing()):
            json_packet = None

            try:
                json_packet = json.loads(data)
            except Exception:
                logging.info('callable_receive_connection: Failed to parse json_packet')

            if json_packet:
                response = await self.handle_received_packet(json_packet, cliconn.bot_context)

                if response:
                    await cliconn.write_packet(response)

            data = await cliconn.read_data()

        if not cliconn.is_closing():
            cliconn.close()

        await cliconn.wait_closed()

        self.active_connections.remove(cliconn)
        logging.info(f'callable_receive_connection: Closing connection for {peername}')

    async def handle_received_packet(self, packet, persistent_bot_context: BotContext):
        # Packet em JSON:
        # {
        #     "type": "command_request",
        #     "data": "echo teste 1 2 3"
        # }
        type = packet.get('type', None)
        data = packet.get('data', None)

        if type and type in self.handlers:
            if not data:
                logging.warn(f'handle_received_packet: Received packet without data')
            
            return await self.handlers[type](data, persistent_bot_context)
        else:
            logging.info(f'handle_received_packet: Received unknown packet type: {type}')

    async def handle_command_request(self, data, persistent_bot_context: BotContext):
        # Arg data pode ser um dict ou uma string ou até mesmo None
        logging.info(f'handle_command_request: Trying to handle command request for data: {data}')
        
        if not data:
            return

        current_context = CliContext(
            self.bot,
            data,
            io.StringIO(),
            persistent_bot_context
        )

        await self.bot.handle_cli_command_parse(
            current_context,
            data
        )

        return {
            "type": "command_response",
            "data": current_context.extract_output_data()
        }
    
    def close_all_active_connections(self):
        for conn in self.active_connections:
            conn.close()

    def transmit_message_to_all_active_connections(self, message: discord.Message):
        for cliconn in self.active_connections:
            asyncio.create_task(
                cliconn.write_packet(
                    {
                        'type': 'message',
                        'data': {
                            'channel': {'id': message.channel.id, 'name': message.channel.name} if message.channel and isinstance(message.channel, discord.TextChannel) else None,
                            'message': {'id': message.id,'content': message.content},
                            'author': {'id': message.author.id,'name': message.author.name}
                        }
                    }
                )
            )

class CEcho(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'echo',
            aliases = ['ec'],
            usage = '[texto...]'
        )

    async def run(self, ctx, args, flags):
        return args

class CHelp(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'help',
            aliases = ['h']
        )
    
    async def run(self, ctx, args, flags):
        return [f'{c.name}' for c in self.bot.clicommands.get_all_commands()]

class CReload(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'reload',
            aliases = ['rl']
        )

    async def run(self, ctx, args, flags):
        try:
            await self.bot.reload_all_modules()
            return 'Todos os modulos foram recarregados.'
        except Exception as e:
            raise CommandError(f'Ocorreu um erro ao tentar realizar o reload:\n\n{type(e).__name__}: {e}')

class CShutdown(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'shutdown',
            aliases = ['sd']
        )

    async def run(self, ctx, args, flags):
        asyncio.create_task(
            self.bot.stop()
        )

        return 'Desligando...'

class CSetContext(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'setcontext',
            aliases = ['ctx'],
            usage = 'id [-u|--user] [-c|--channel]'
        )

    async def run(self, ctx, args, flags):
        if not args:
            return self.get_usage_text()

        try:
            target_id = int(args[0])
        except ValueError:
            raise CommandError('O ID informado não é um número válido.')

        if 'u' in flags or 'user' in flags:
            # @NOTE:
            # Estamos usando o BotContext.author como se fosse um target user e não como um author realmente...
            # Isso semânticamente está meio errado, porém, no contexto de um comando CLI, quem é o autor dos comandos é sempre a outra ponta da conexão
            # Então assumir que exista um autor de objeto aqui não faria sentido também.
            target = self.bot.client.get_user(target_id)

            if not target:
                raise CommandError(f'O usuário {target_id} não foi encontrado.')
            else:
                ctx.update_botcontext_target(target)
        elif 'c' in flags or 'channel' in flags:
            target = self.bot.client.get_channel(target_id)

            if not target:
                raise CommandError(f'O canal {target_id} não foi encontrado.')
            else:
                ctx.update_botcontext_target(target)
        else:
            return self.get_usage_text()

        return 'O contexto dos comandos foi alterado!'
        
class CSay(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'say',
            aliases = ['s'],
            usage = '[texto...]'
        )

    async def run(self, ctx, args, flags):
        try:
            await ctx.say(args)
        except Exception as e:
            raise CommandError(f'Ocorreu um erro ao tentar responder o contexto atual:\n\n{type(e).__name__}: {e}')
