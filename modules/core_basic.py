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

    async def run(self, ctx, args, flags):
        if not args:
            return self.get_usage_embed(ctx)

        return args

class CSay(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'say',
            aliases = ['s'],
            description = "Faz com que o bot fale a mensagem informada.",
            usage = "[texto...]"
        )

    async def run(self, ctx, args, flags):
        if not args:
            return self.get_usage_embed(ctx)
        
        # @HACK: Utiliza o método diretamente para poder fazer com que o bot não utilize embeds por padrão
        await ctx.reply(args, use_embed_as_default=False)

        # Força a PIPELINE a não poder continuar
        return None

class CFullwidth(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'fullwidth',
            aliases = ['fw', 'vaporwave'],
            description = "Converte a mensagem recebida em uma mensagem com caracteres Ｕｎｉｃｏｄｅ　Ｆｕｌｌ-Ｗｉｄｔｈ.",
            usage = "[texto...]"
        )

    async def run(self, ctx, args, flags):
        if not args:
            return self.get_usage_embed(ctx)

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

    async def run(self, ctx, args, flags):
        if not args:
            return self.get_usage_embed(ctx)

        return f"👏 {' 👏 '.join(args)} 👏"

class CDateFormat(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'dateformat',
            aliases = ['datefmt'],
            description = "Retorna a data ou horário formatado de acordo com a string informada (Ex: %H:%M:%S ou %d/%m/%Y).",
            usage = 'formato',
            hidden = True
        )

    async def run(self, ctx, args, flags):
        if not args:
            return self.get_usage_embed(ctx)

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
            aliases = ['tm'],
            command = 'dateformat %H:%M:%S',
            description = 'Retorna o horário atual dado pelo formato %H:%M:%S.',
            hidden = True
        )

class CDate(InterpretedCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'date',
            aliases = ['dt'],
            command = 'dateformat %d/%m/%Y',
            description = 'Retorna a data atual dado pelo formato %d/%m/%Y.',
            hidden = True
        )

class CFormat(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'format',
            aliases = ['fmt'],
            description = "Aplica todas as alterações passadas por argumento.",
            usage = "[-u|--upper] [-l|--lower] [-r|--reverse]",
            hidden = True
        )

    def transform(self, transf: str, flags: dict):
        for flag in flags.keys():
            if flag in ('u', 'upper'):
                transf = transf.upper()
            elif flag in ('l', 'lower'):
                transf = transf.lower()
            elif flag in ('r', 'reverse'):
                transf = transf[::-1]

        return transf

    async def run(self, ctx, args, flags):
        if not args:
            return self.get_usage_embed(ctx)

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

    async def run(self, ctx, args, flags):
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
            description = "Calcula a expressão matemática informada (Ex: 1 + 2 (2 / 4) * 9), atualmente suporta os operadores: +, -, *, /, ^ e %.",
            usage = "[expressao...]"
        )

    async def run(self, ctx, args, flags):
        if not args:
            return self.get_usage_embed(ctx)

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
            usage = "[@Usuario] [--self] [--name] [--id] [--nick] [--display_name] [--mention] [--permissionlevel]",
            hidden = True
        )

        self.allowed_attr = ('name', 'id', 'nick', 'display_name', 'guild', 'joined_at', 'status', 'mention')

    async def run(self, ctx, args, flags):
        users = flags.get('mentions', None)
        
        if 'self' in flags:
            target = ctx.author
        else:
            target = users[0] if users else None

        if not target:
            return self.get_usage_embed(ctx)

        # @HACK: Atribuir target como se fosse o novo author da mensagem
        ctx.author = target

        ret = []

        for key in flags.keys():
            if key == 'permissionlevel':
                ret.append(self.bot.rate_author_permission_level(ctx).name)
            elif key in self.allowed_attr:
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

    async def run(self, ctx, args, flags):
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

class CCount(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "count",
            aliases = ['co'],
            description = "Retorna o tamanho da lista de argumentos recebidos.",
            hidden = True
        )

    async def run(self, ctx, args, flags):
        return str(len(args))

class CLen(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "len",
            aliases = ['le'],
            description = "Retorna a soma do tamanho de todos os argumentos recebidos.",
            hidden = True
        )

    async def run(self, ctx, args, flags):
        ilen = 0
        for a in args:
            ilen += len(a)

        return str(ilen)

class CSubstr(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "substr",
            aliases = ['sub'],
            description = "Retorna uma substring dos argumentos recebidos como uma única string.",
            usage = 'texto [--start=0] [--end=-1]',
            hidden = True
        )

    async def run(self, ctx, args, flags):
        if not args:
            return self.get_usage_embed(ctx)

        en = None

        try:
            st = int(flags.get('start', '0'))

            if 'end' in flags:
                en = int(flags['end'])
        except ValueError:
            raise CommandError('As flags `--start` e `--end` não possuem um formato de número válido.')

        try:
            joined_args = ' '.join(args)
            return joined_args[st:en] if en != None else joined_args[st:]
        except IndexError:
            raise CommandError('O alcance de índices informados não são válidos (start={st}, end={en}).')