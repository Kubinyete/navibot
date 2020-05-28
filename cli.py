#!/usr/bin/python3
# Cliente capaz de abrir um conexão com o bot para poder enviar e receber comandos da CLI.
import asyncio
import termios
import sys
import json
import socket
import io
import select

class ClientApp:
    def __init__(self, host: str, port: int, timeout: int=5):
        self.host = host
        self.port = port
        self.timeout = timeout

        self.loop = asyncio.get_event_loop()

        self.prev_term_attr = None
        self.is_exiting = False
        self.command_buffer = io.StringIO()
        self.input_chars_written = 0

        self.pending_read_packet_task = None

    def prepare_terminal(self):
        assert self.prev_term_attr is None

        saved = termios.tcgetattr(sys.stdin)
        curr = termios.tcgetattr(sys.stdin)
        
        # Desativa o ECHO do console
        curr[3] = curr[3] & ~termios.ECHO
        # Desativa o modo CANONICAL do console
        curr[3] = curr[3] & ~termios.ICANON

        self.prev_term_attr = saved

        # Aplica as modificações
        termios.tcsetattr(sys.stdin, termios.TCSANOW, curr)

    def rollback_terminal(self):
        assert self.prev_term_attr != None

        termios.tcsetattr(sys.stdin, termios.TCSANOW, self.prev_term_attr)

    def run(self):
        try:
            self.prepare_terminal()

            self.loop.run_until_complete(
                self.arun()
            )
            
            self.write(f'Exiting gracefully...')
        except KeyboardInterrupt:
            self.write(f'KeyboardInterrupt received, exiting CLI...')
        except Exception as e:
            print(f'ERROR: {type(e).__name__}: {e}')
        finally:
            self.rollback_terminal()

    async def arun(self):
        assert self.loop

        print(f'Connecting to {self.host}:{self.port}...')
        reader, writer = await asyncio.open_connection(
            host=self.host,
            port=self.port,
            loop=self.loop
        )

        # Fica processando comandos da stdin ao mesmo tempo que lida com pacotes de resposta
        return await asyncio.gather(
            self.handle_input_loop(writer),
            self.handle_recv_packet_loop(reader)
        )

    def write_input(self, newline: bool=False, force: bool=False):
        inputslen = self.command_buffer.tell()

        if newline or force or inputslen != self.input_chars_written:
            inputs = self.command_buffer.getvalue()
            self.input_chars_written = inputslen

            # Vai para o inicio da linha
            sys.stdout.write("\033[1G")
            # Limpa a linha atual (pode conter um Input anterior)
            sys.stdout.write("\033[0K")
            # Volta o input
            sys.stdout.write(f'\033[1;35mNavibot\033[0m \033[1;31m$\033[0m {inputs}')
            
            if newline:
                self.command_buffer.seek(0)
                self.command_buffer.truncate(0)                
                self.input_chars_written = 0

                sys.stdout.write("\n")
                sys.stdout.write(f'\033[1;35mNavibot\033[0m \033[1;31m$\033[0m ')
            
            # Pede para dar flush na stdout
            sys.stdout.flush()

    def write(self, msg: str):
        # Vai para o inicio da linha
        sys.stdout.write("\033[1G")
        # Limpa a linha atual (pode conter um Input anterior)
        sys.stdout.write("\033[0K")
        # Manda a mensagem
        sys.stdout.write(f'{msg}\n')
        
        # Volta o input do usuário
        self.write_input(False, True)

    async def handle_input_loop(self, writer: asyncio.StreamWriter):
        self.write_input(False, True)

        while not self.is_exiting:
            await self.handle_recv_input(writer)
            await asyncio.sleep(0.033)

    async def handle_recv_input(self, writer: asyncio.StreamWriter):
        while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            byte = sys.stdin.read(1)
            
            if byte == '\r':
                continue
            elif byte == '\x7f':
                # Backspace
                if self.command_buffer.tell() > 0:
                    self.command_buffer.truncate(self.command_buffer.tell() - 1)
                    self.command_buffer.seek(self.command_buffer.tell() - 1)
            elif byte == '\x1b':
                # @TODO:
                # Esqueci exatamente qual é esse código, mas sei que tem haver com "teclas compostas"
                pass
            elif byte == '\n':
                await self.handle_receive_command(writer, self.command_buffer.getvalue())
                self.write_input(True)
            else:
                self.command_buffer.write(byte)
            
            self.write_input()

    async def handle_receive_command(self, writer: asyncio.StreamWriter, command_string: str):
        if command_string in ('exit', 'quit'):
            self.is_exiting = True

            if self.pending_read_packet_task:
                self.pending_read_packet_task.cancel()
        else:
            await self.handle_send_packet(
                writer, 
                {
                    'type': 'command_request',
                    'data': command_string
                }
            )

    async def handle_recv_packet_loop(self, reader: asyncio.StreamReader):
        while not self.is_exiting:
            try:
                self.pending_read_packet_task = asyncio.create_task(reader.readline())
                data = await self.pending_read_packet_task

                while data:
                    try:
                        json_packet = json.loads(data)
                    except Exception as e:
                        self.write(f'ERROR: Received invalid json_packet from server: {type(e).__name__}: {e}')
                        return

                    await self.handle_receive_packet(json_packet)
                    
                    self.pending_read_packet_task = asyncio.create_task(reader.readline())
                    data = await self.pending_read_packet_task
            except asyncio.CancelledError:
                # self.write('Running task pending_read_packet_task was cancelled')
                pass

    async def handle_receive_packet(self, packet: dict):
        type = packet.get('type', None)
        data = packet.get('data', None)

        try:
            if type == 'command_response':
                if data:
                    self.write(str(data))
            elif type == 'message':
                channel_name = f"#{data['channel']['name']} {data['channel']['id']}" if data['channel'] else 'Direct Message'
                author_name = data['author']['name']
                content  = data['message']['content']

                self.write(f'\033[1;33m[{channel_name}]\033[0m <\033[4;31m{author_name}\033[0m>: {content}')
            else:
                self.write(f'ERROR: Received invalid packet type from server')
        except IndexError:
            self.write(f'ERROR: Received packet but missing a key value, skipping...')

    async def handle_send_packet(self, writer: asyncio.StreamWriter, packet: dict):
        writer.write((json.dumps(packet) + '\n').encode('utf-8'))
        await writer.drain()

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    port = 7777

    if len(sys.argv) > 2:
        try:
            port = int(sys.argv[2])
        except ValueError:
            sys.stdout.write(f'Failed to parse port number, using default = {port}\n')

    app = ClientApp(
        host,
        port
    )

    app.run()
