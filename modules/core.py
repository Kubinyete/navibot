import discord
import random
import inspect
import asyncio
import logging
import time
import datetime
import math
import aiohttp

from navibot.client import BotCommand, CommandAlias, TimeoutContext, PermissionLevel
from navibot.errors import CommandError
from navibot.util import is_instance, seconds_string, parse_timespan_seconds, timespan_seconds, string_fullwidth_alphanumeric

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

        return f"{random.randint(minv, maxv)}"

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

class CSetAvatar(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "setavatar",
            aliases = ['stavatar'],
            description = "Edita o perfil do bot atual, recebe um URL da imagem nova de perfil, a qual será baixada e enviada.",
            usage = "{name} URL",
            permissionlevel = PermissionLevel.BOT_OWNER
        )

        self.httpsession = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        avatar_url = ''.join(args)
        avatar_bytes = None

        try:
            async with self.httpsession.get(avatar_url) as resp:
                if resp.status == 200:
                    avatar_bytes = await resp.read()
                else:
                    raise CommandError("Não foi possível obter o novo avatar através da URL fornecida, o destino não retornou OK.")
        except aiohttp.ClientError:
            raise CommandError("Não foi possível obter o novo avatar através da URL fornecida.")

        try:
            # user.edit() pode travar caso ultrapassarmos o limite e ficarmos de cooldown ou se o upload estiver demorando muito (não seria comum neste caso).
            await asyncio.wait_for(
                self.bot.client.user.edit(
                    avatar=avatar_bytes
                ), 60
            )
        except discord.InvalidArgument as e:
            logging.error(e)
            raise CommandError("O formato de imagem fornecido não é suportado pelo Discord, favor informar os formatos (JPEG, PNG).")
        except discord.HTTPException as e:
            logging.error(e)
            raise CommandError("Não foi possível editar o perfil do bot.")
        except asyncio.TimeoutError as e:
            logging.error(e)
            raise CommandError("Não foi possível editar o perfil do bot, o tempo limite de envio foi excedido.")
            
        await message.add_reaction('✅')

class CSetName(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "setname",
            aliases = ['stname'],
            description = "Edita o perfil do bot atual, recebe um novo nome de usuário.",
            usage = "{name} [nome...]",
            permissionlevel = PermissionLevel.BOT_OWNER
        )

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        username = ' '.join(args)

        try:
            # user.edit() pode travar caso ultrapassarmos o limite e ficarmos de cooldown.
            await asyncio.wait_for(
                self.bot.client.user.edit(
                    username=username
                ), 10
            )
        except (discord.InvalidArgument, discord.HTTPException, asyncio.TimeoutError) as e:
            logging.error(e)
            raise CommandError("Não foi possível editar o perfil do bot.")
            
        await message.add_reaction('✅')

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
        return f"{datetime.datetime.now().strftime('%H:%M:%S')}"

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
        return f"{datetime.datetime.now().strftime('%d/%m/%Y')}"

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

        return random.choice(args)

class CGuildVariables(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'guildvars',
            aliases = ['gv', 'gvars'],
            description = "Gerencia as variáveis da Guild atual.",
            usage = "{name} variavel [novo valor] [--list]",
            # Nível de permissão temporário
            permissionlevel=PermissionLevel.BOT_OWNER
        )

    async def run(self, message, args, flags):
        if not isinstance(message.channel, discord.TextChannel):
            raise CommandError('Comando indisponível fora do contexto de uma Guild.')

        gsm = self.get_guild_settings_manager()
        gvars = await gsm.get_guild_variables(message.channel.guild.id)

        if 'list' in flags:
            text = ''
            for key, value in gvars.items():
                text += f'**{value.valuetype.name.lower()}**:`{key}` = `{value.value}`\n'

            return text
        else:
            if args:
                try:
                    expected_variable = gvars[args[0]]
                except KeyError:
                    raise CommandError(f'A variável `{args[0]}` não existe no contexto da Guild atual.')

                if len(args) > 1:
                    new_value = ' '.join(args[1:])
                    prev_value = expected_variable.get_value()

                    try:
                        expected_variable.set_value(new_value)
                    except ValueError:
                        raise CommandError(f'A variável `{args[0]}` não recebeu um tipo de dados coerente, **{value.valuetype.name.lower()}** esperado.')

                    if await gsm.update_guild_variable(expected_variable):
                        await message.add_reaction('✅')
                    else:
                        expected_variable.set_value(prev_value)
                        raise CommandError(f'Não foi possível modificar o valor da variável `{args[0]}`.')
                else:
                    return f'**{expected_variable.valuetype.name.lower()}**:`{expected_variable.key}` = `{expected_variable.value}`\n'
            else:
                return self.get_usage_embed(message)
