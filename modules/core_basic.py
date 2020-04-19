import logging

from datetime import datetime
from random import randint, choice

from navibot.client import BotCommand, InterpretedCommand
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
            usage = "[texto...]"
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
            usage = "[texto...]"
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
            usage = "[texto...]"
        )

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        return f":clap: {' :clap: '.join(args)} :clap:"

class CDateFormat(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'dateformat',
            aliases = ['datefmt'],
            description = "Retorna a data ou horário formatado de acordo com a string informada (Ex: %H:%M:%S ou %d/%m/%Y).",
            usage = 'formato'
        )

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        fmt = ' '.join(args)

        try:
            return datetime.now().strftime(fmt)
        except Exception as e:
            raise CommandError(f'Não foi possível formatar a data de acordo com o formato `{fmt}` informado:\n\n`{e}`')

class CTime(InterpretedCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'time',
            command = 'dateformat %H:%M:%S'
        )

class CDate(InterpretedCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'date',
            command = 'dateformat %d/%m/%Y'
        )

class CFormat(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'format',
            aliases = ['fmt'],
            description = "Aplica todas as alterações passadas por argumento.",
            usage = "[-u|--upper] [-l|--lower] [-r|--reverse]"
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
            usage = "[arg1] [argN...]"
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
            aliases = ['dice'],
            description = "Retorna um número aleatório entre [min] e [max].",
            usage = "[min=0] [max=6]"
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
            raise CommandError("É preciso informar números inteiros válidos.")

        return f"{randint(minv, maxv)}"

class CExpressionParser(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "expr",
            aliases = ['calc', 'bc'],
            description = "Calcula a expressão matemática informada (Ex: 1 + 2 (2 / 4) * 9).",
            usage = "[expressao...]"
        )

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        try:
            return str(ExpressionParser(' '.join(args)).parse().evaluate())
        except ParserError as e:
            raise CommandError(f'Ocorreu um erro durante a execução do parser:\n\n`{e}`')
        except OverflowError:
            raise CommandError('O número recebido ultrapassa o tamanho permitido pela plataforma.')
        except ZeroDivisionError:
            raise CommandError('Divisão por zero não permitida.')

class CGetMember(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "getmember",
            aliases = ['member'],
            description = "Retorna uma ou mais propriedades desejadas do membro mencionado.",
            usage = "[@Usuario] [--self] [--name] [--id] [--nick] [--display_name] [--mention]",
            hidden = True
        )

        self.allowed_attr = ('name', 'id', 'nick', 'display_name', 'guild', 'joined_at', 'status', 'mention')

    async def run(self, message, args, flags):
        users = flags.get('mentions', None)
        
        if 'self' in flags:
            target = message.author
        else:
            target = users[0] if users else None

        if not target:
            return self.get_usage_embed(message)

        ret = []

        for key in flags.keys():
            if key in self.allowed_attr:
                tmp = getattr(target, key, None)

                if tmp:
                    ret.append(str(tmp))

        return ret

class CGetArg(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "getarg",
            aliases = ['arg'],
            description = "Retorna uma ou mais argumentos recebidos de um comando interpretado que seja o ativador.",
            usage = "indice [--all]",
            hidden = True
        )

    async def run(self, message, args, flags):
        pipeline_args = flags.get('activator_args', None)
        
        if pipeline_args is None:
            raise CommandError('Este comando só pode ser executado quando for solicitado por um comando interpretado anteriormente na PIPELINE.')

        if 'all' in flags:
            return pipeline_args
        else:
            indice = -1
            if args:
                try:
                    indice = int(args[0])
                except ValueError:
                    pass

            if indice >= 0 and indice < len(pipeline_args):
                return pipeline_args[indice]
            else:
                raise CommandError('É preciso informar um indice válido.')

class CArgCount(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "argcount",
            aliases = ['argc'],
            description = "Retorna o tamanho da lista de argumentos recebidos.",
            hidden = True
        )

    async def run(self, message, args, flags):
        return str(len(args))

class CTeste(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "teste",
            hidden = True
        )

    async def run(self, message, args, flags):
        return "Olá mundo!"