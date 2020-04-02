from datetime import datetime
from random import randint, choice

from navibot.client import BotCommand
from navibot.errors import CommandError
from navibot.util import string_fullwidth_alphanumeric

class CEcho(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'echo',
            aliases = ['ec'],
            description = "Faz com que o bot repita a mensagem informada.",
            usage = "{name} [texto...]"
        )

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        return ' '.join(args)

class CFullwidth(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'fullwidth',
            aliases = ['fw', 'vaporwave'],
            description = "Converte a mensagem recebida em uma mensagem com caracteres Ｕｎｉｃｏｄｅ　Ｆｕｌｌ-Ｗｉｄｔｈ.",
            usage = "{name} [texto...]"
        )

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        return string_fullwidth_alphanumeric(' '.join(args))

class CClap(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'clap',
            aliases = ['cl'],
            description = "Converte a mensagem recebida em uma mensagem com :clap: embutidos.",
            usage = "{name} [texto...]"
        )

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        return f":clap: {' :clap: '.join(args)} :clap:"

class CTime(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'time',
            aliases = ['tm'],
            description = "Retorna o horário atual.",
            usage = "{name}"
        )

    async def run(self, message, args, flags):
        return f"{datetime.now().strftime('%H:%M:%S')}"

class CDate(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'date',
            aliases = ['dt'],
            description = "Retorna a data atual.",
            usage = "{name}"
        )

    async def run(self, message, args, flags):
        return f"{datetime.now().strftime('%d/%m/%Y')}"

class CFormat(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'format',
            aliases = ['fmt'],
            description = "Aplica todas as alterações passadas por argumento.",
            usage = "{name} [-u|--upper] [-l|--lower] [-r|--reverse]"
        )

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        transf = ' '.join(args)

        for flag in flags.keys():
            if flag in ('u', 'upper'):
                transf = transf.upper()
            elif flag in ('l', 'lower'):
                transf = transf.lower()
            elif flag in ('r', 'reverse'):
                transf = transf[::-1]

        return transf

class CChoice(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'choice',
            aliases = ['cc'],
            description = "Escolhe aleatóriamente um dos argumentos informados.",
            usage = "{name} [arg1] [argN...]"
        )

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        return choice(args)

class CRoll(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "roll",
            aliases = ['r'],
            description = "Retorna um número aleatório entre [min] e [max].",
            usage = "{name} [min] [max]"
        )

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
            raise CommandError(F"É preciso informar números inteiros válidos.")

        return f"{randint(minv, maxv)}"