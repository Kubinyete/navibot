import logging

from datetime import datetime
from random import randint, choice

from navibot.client import BotCommand
from navibot.errors import CommandError, ParserError
from navibot.util import string_fullwidth_alphanumeric
from navibot.parser import ExpressionParser

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

        return args

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

        return [string_fullwidth_alphanumeric(arg) for arg in args]

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

    def transform(self, transf, flags):
        for flag in flags.keys():
            if flag in ('u', 'upper'):
                transf = transf.upper()
            elif flag in ('l', 'lower'):
                transf = transf.lower()
            elif flag in ('r', 'reverse'):
                transf = transf[::-1]

        return transf

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        return [self.transform(transf, flags) for transf in args]

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

class CExpressionParser(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "expr",
            aliases = ['calc', 'bc'],
            description = "Calcula a expressão matemática informada (Ex: 1 + 2 (2 / 4) * 9).",
            usage = "{name} [expressao...]"
        )

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        try:
            return str(ExpressionParser(''.join(args)).parse().evaluate())
        except ParserError as e:
            raise CommandError(f'Ocorreu um erro durante a execução do parser:\n{e}')
        except OverflowError:
            raise CommandError(f'O número recebido ultrapassa o tamanho permitido pela plataforma.')
        except ZeroDivisionError:
            raise CommandError(f'Divisão por zero não permitida.')

class CGetMember(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "getmember",
            aliases = ['gmember', 'gmem'],
            description = "Retorna uma ou mais propriedades desejadas do membro mencionado.",
            usage = "{name} [--name|--id|--nick|--display_name]"
        )

        self.allowed_attr = ('name', 'id', 'nick', 'display_name', 'guild', 'joined_at', 'status')

    async def run(self, message, args, flags):
        users = flags.get('mentions', None)
        
        target = users[0] if users else None

        if not target:
            return self.get_usage_embed(message)

        ret = []

        for key, value in flags.items():
            if key in self.allowed_attr:
                tmp = getattr(target, key, None)

                if tmp:
                    ret.append(str(tmp))

        return ret