import discord
import random
import inspect
import asyncio
import logging
import time
import datetime
import math
import navibot
import naviutil

class CHelp(navibot.BotCommand):
    def initialize(self):
        self.name = "help"
        self.aliases = ['h']
        self.description = "Demonstra informações sobre todos os comandos disponibilizados."
        self.usage = f"{self.name} [cmd]"

    async def run(self, message, args, flags):
        text = "**NaviBot** é um bot **experimental** escrito utilizando a biblioteca [discord.py](https://github.com/Rapptz/discord.py) por razões de aprendizado, mais específicamente para experimentar com o asyncio e também conseguir construir e replicar algumas funcionalidades que já vi serem implementadas."
        text += f"\n\n:information_source: Digite `help [comando]` para obter mais informações."
        text += f"\n\n**Comandos disponíveis**:\n\n"

        if args:
            target = args[0]
            target = self.bot.commands.get(target, None)

            if target:
                target = target.origin if naviutil.is_instance(target, navibot.CommandAlias) else target
                return target.get_usage_embed(message)
            else:
                raise navibot.CommandError(f"O comando `{args[0]}` não existe.")

        for key, value in self.bot.commands.items():
            if naviutil.is_instance(value, navibot.CommandAlias):
                continue

            typestr = type(value).__name__
            mdlstr = type(value).__module__

            text += f"`{key}` ({mdlstr}.{typestr})\n"

        embed = self.create_response_embed(message, text)
        embed.title = "NaviBot"

        return embed

class CRoll(navibot.BotCommand):
    def initialize(self):
        self.name = "roll"
        self.aliases = ['r']
        self.description = "Retorna um número aleatório entre [min] e [max]."
        self.usage = f"{self.name} [min] [max]"

    async def run(self, message, args, flags):
        minv = 0
        maxv = 6

        try:
            if len(args) >= 2:
                minv = int(args[0])
                maxv = int(args[1])
            elif args:
                maxv = int(args[0])

            assert minv >= 0
            assert minv <= maxv
        except (ValueError, AssertionError):
            raise navibot.CommandError(F"É preciso informar números inteiros válidos.")

        return f"{random.randint(minv, maxv)}"

class CAvatar(navibot.BotCommand):
    def initialize(self):
        self.name = "avatar"
        self.aliases = ['av']
        self.description = "Retorna o avatar do indivíduo mencionado."
        self.usage = f"{self.name} @Usuario [--url] [--size=256]"

    async def run(self, message, args, flags):
        target = message.mentions[0] if message.mentions else None

        if not target:
            return self.get_usage_embed(message)

        try:
            size = int(flags.get('size', 256))
            size = int(math.pow(2, math.floor(math.log2(size))))

            assert size >= 16 and size <= 4096
        except ValueError:
            raise navibot.CommandError(F"É preciso informar números inteiros válidos.")
        except AssertionError:
            raise navibot.CommandError("O argumento `--size` deve estar entre 16 e 4096 e ser uma potência de 2 (Ex: 32, 64, 128...).")

        out = None

        if "url" in flags:
            out = str(target.avatar_url_as(size=size))
        else:
            out = self.create_response_embed(message) 
            out.title = f"Avatar de {target.name}"
            out.set_image(url=target.avatar_url_as(size=256))
        
        return out

class CRemind(navibot.BotCommand):
    def initialize(self):
        self.name = "remind"
        self.aliases = ['re']
        self.description = "Registra um determinado lembrete de acordo com o tempo de espera `--time` informado."
        self.usage = f"{self.name} --time=1h30m [lembrete...]"
        self.enable_usermap = True

        # Isso é chamado durante o construtor suoer().__init__(), portanto, podemos adicionar novos atributos
        self.limit = 3

    async def run(self, message, args, flags):
        if not 'time' in flags and not 'list' in flags:
            return self.get_usage_embed(message)
        
        stored = self.get_user_storage(message.author)

        if 'list' in flags:
            text = '\n'.join([f":bell: `{context.kwargs.get('text')}`, expira em *{naviutil.seconds_string(math.ceil(context.kwargs.get('timestamp') + context.waitfor - time.time()))}*" for context in stored])
            return text if text else ":information_source: Você não registrou nenhum lembrete até o momento."

        text = ' '.join(args) if args else ''

        seconds = naviutil.parse_timespan_seconds(flags['time'])

        if not seconds or seconds > naviutil.timespan_seconds((24, 'h')):
            raise navibot.CommandError(f"O tempo de espera `--time` informado não está em um formato válido ou ultrapassa o limite de 24 horas.")

        if len(stored) < self.limit:
            t = navibot.TimeoutContext(seconds, self.callable_send_reminder, callback=self.callable_free_reminder, author=message.author, text=text if text else f"Lembrete #{len(stored) + 1}", timestamp=time.time())
            stored.append(t)
            t.create_task()
            await message.add_reaction('✅')
        else:
            raise navibot.CommandError(f"Você atingiu o limite de {self.limit} lembretes registrados, por favor tente mais tarde.")
        
    async def callable_send_reminder(self, reminder, kwargs):
        author = kwargs.get('author', None)
        text = kwargs.get('text', None)

        assert author

        await author.send(f":bell: Olá <@{author.id}>, estou te avisando sobre um **lembrete**!" if not text else f":bell: Olá <@{author.id}>, estou te avisando sobre:\n`{text}`")

    async def callable_free_reminder(self, reminder, kwargs):
        author = kwargs.get('author', None)
        assert author

        stored = self.get_user_storage(author)
        assert stored

        try:
            stored.remove(reminder)
        except ValueError:
            logging.error(f"callback_free_reminder > Failed to remove {type(reminder)} from storage, context = {reminder}")

class CEcho(navibot.BotCommand):
    def initialize(self):
        self.name = 'echo'
        self.aliases = ['ec']
        self.description = "Faz com que o bot repita a mensagem informada."
        self.usage = f"{self.name} [texto...]"

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        return ' '.join(args)

class CFullwidth(navibot.BotCommand):
    def initialize(self):
        self.name = 'fullwidth'
        self.aliases = ['fw', 'vaporwave']
        self.description = "Converte a mensagem recebida em uma mensagem com caracteres Ｕｎｉｃｏｄｅ　Ｆｕｌｌ-Ｗｉｄｔｈ."
        self.usage = f"{self.name} [texto...]"

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        return naviutil.string_fullwidth_alphanumeric(' '.join(args))

class CClap(navibot.BotCommand):
    def initialize(self):
        self.name = 'clap'
        self.aliases = ['cl']
        self.description = "Converte a mensagem recebida em uma mensagem com :clap: embutidos."
        self.usage = f"{self.name} [texto...]"

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        return f":clap: {' :clap: '.join(args)} :clap:"

class CTime(navibot.BotCommand):
    def initialize(self):
        self.name = 'time'
        self.aliases = ['tm']
        self.description = "Retorna o horário atual."
        self.usage = f"{self.name}"

    async def run(self, message, args, flags):
        return f"{datetime.datetime.now().strftime('%H:%M:%S')}"

class CDate(navibot.BotCommand):
    def initialize(self):
        self.name = 'date'
        self.aliases = ['dt']
        self.description = "Retorna a data atual."
        self.usage = f"{self.name}"

    async def run(self, message, args, flags):
        return f"{datetime.datetime.now().strftime('%d/%m/%Y')}"