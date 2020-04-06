import asyncio
import logging
import time
import datetime
import math

from navibot.client import BotCommand, CommandAlias, TimeoutContext, PermissionLevel
from navibot.errors import CommandError
from navibot.util import is_instance, seconds_string, parse_timespan_seconds, timespan_seconds

class CHelp(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "help",
            aliases = ['h'],
            description = "Demonstra informações sobre todos os comandos disponibilizados.",
            usage = "{name} [cmd]"
        )

    async def run(self, message, args, flags):
        text = "**NaviBot** é um bot **experimental** escrito utilizando a biblioteca [discord.py](https://github.com/Rapptz/discord.py) por razões de aprendizado, mais específicamente para experimentar com o asyncio e também conseguir construir e replicar algumas funcionalidades que já vi serem implementadas."
        text += f"\n\n:information_source: Digite `help [comando]` para obter mais informações."
        text += f"\n\n**Comandos disponíveis**:\n\n"

        if args:
            target = args[0]
            target = self.bot.commands.get(target, None)

            if target:
                target = target.origin if is_instance(target, CommandAlias) else target
                return target.get_usage_embed(message)
            else:
                raise CommandError(f"O comando `{args[0]}` não existe.")

        for key, value in self.bot.commands.items():
            if is_instance(value, CommandAlias):
                continue

            typestr = type(value).__name__
            mdlstr = type(value).__module__

            text += f"`{key}` ({mdlstr}.{typestr})\n"

        embed = self.create_response_embed(message, text)
        embed.title = "NaviBot"

        return embed

class CAvatar(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "avatar",
            aliases = ['av'],
            description = "Retorna o avatar do indivíduo mencionado.",
            usage = "{name} @Usuario [--url] [--size=256]"
        )

    async def run(self, message, args, flags):
        target = message.mentions[0] if message.mentions else None

        if not target:
            return self.get_usage_embed(message)

        try:
            size = int(flags.get('size', 256))
            size = int(math.pow(2, math.floor(math.log2(size))))

            assert size >= 16 and size <= 4096
        except ValueError:
            raise CommandError(F"É preciso informar números inteiros válidos.")
        except AssertionError:
            raise CommandError("O argumento `--size` deve estar entre 16 e 4096 e ser uma potência de 2 (Ex: 32, 64, 128...).")

        out = None

        if "url" in flags:
            out = str(target.avatar_url_as(size=size))
        else:
            out = self.create_response_embed(message) 
            out.title = f"Avatar de {target.name}"
            out.set_image(url=target.avatar_url_as(size=256))
        
        return out

class CRemind(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "remind",
            aliases = ['re'],
            description = "Registra um determinado lembrete de acordo com o tempo de espera `--time` informado.",
            usage = "{name} --time=1h30m [--list] [--remove=ID] [--clear] [lembrete...]",
            enable_usermap = True
        )

        self.limit = 3

    async def run(self, message, args, flags):
        stored = self.get_user_storage(message.author)

        if 'list' in flags:
            if stored:
                text = ''

                i = 0
                for context in stored:
                    text += f"[{i}] :bell: `{context.kwargs.get('text')}`, expira em *{seconds_string(math.ceil(context.kwargs.get('timestamp') + context.waitfor - time.time()))}*\n"
                    i += 1

                return text
            else:
                return ":information_source: Você não registrou nenhum lembrete até o momento."
        elif 'remove' in flags:
            if not stored:
                return ":information_source: Você não registrou nenhum lembrete até o momento."

            cid = -1

            try:
                cid = int(flags['remove'])
            except ValueError:
                raise CommandError("É preciso informar um valor válido para o valor de `--remove`.")

            if cid >= 0 and cid < len(stored):
                stored.remove(stored[cid])
                await message.add_reaction('✅')
            else:
                raise CommandError("O identificador informado ao argumento `--remove` não existe.")
        elif 'clear' in flags:
            i = 0
            for context in stored:
                context.running_task.cancel()
                i += 1

            stored.clear()

            return f':information_source: Total de {i} tarefa(s) cancelada(s).'
        else:
            if not 'time' in flags:
                return self.get_usage_embed(message)

            text = ' '.join(args) if args else ''

            seconds = parse_timespan_seconds(flags['time'])

            if not seconds or seconds > timespan_seconds((24, 'h')):
                raise CommandError(f"O tempo de espera `--time` informado não está em um formato válido ou ultrapassa o limite de 24 horas.")

            if len(stored) < self.limit:
                t = TimeoutContext(seconds, self.callable_send_reminder, callback=self.callable_free_reminder, author=message.author, text=text if text else f"Lembrete #{len(stored) + 1}", timestamp=time.time())
                stored.append(t)
                t.create_task()
                await message.add_reaction('✅')
            else:
                raise CommandError(f"Você atingiu o limite de {self.limit} lembretes registrados, por favor tente mais tarde.")
        
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