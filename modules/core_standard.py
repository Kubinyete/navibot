import asyncio
import logging
import time
import datetime
import math
import discord

from navibot.client import BotCommand, CommandAlias, InterpretedCommand, TimeoutContext, PermissionLevel, ReactionType, Slider
from navibot.errors import CommandError
from navibot.util import is_instance, seconds_string, parse_timespan_seconds, timespan_seconds, seconds_string

class CHelp(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "help",
            aliases = ['h'],
            description = "Demonstra informações sobre todos os comandos disponibilizados.",
            usage = "[cmd]"
        )

        self.commands_per_page = 30

    async def run(self, message, args, flags):
        text = "**Navibot** é um bot **experimental** escrito utilizando a biblioteca [discord.py](https://github.com/Rapptz/discord.py) por razões de aprendizado, mais específicamente para experimentar com o asyncio e também conseguir construir e replicar algumas funcionalidades que já vi serem implementadas."
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

        embeds = [self.create_response_embed(message)]
        curr = embeds[0]
        
        i = 1
        for key, value in self.bot.commands.items():
            if is_instance(value, CommandAlias):
                continue
            elif i % self.commands_per_page == 0:
                curr.title = "Navibot"
                curr.description = str(text)

                text = ''

                curr = self.create_response_embed(message)
                embeds.append(curr)

            typestr = type(value).__name__
            mdlstr = type(value).__module__

            text += f"`{key}` ({mdlstr}.{typestr})\n"

            i += 1

        curr.title = "Navibot"
        curr.description = text

        return Slider(
            self.bot,
            message,
            embeds,
            restricted=True
        )

class CAvatar(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "avatar",
            aliases = ['av'],
            description = "Retorna o avatar da Guild ou indivíduo mencionado.",
            usage = "[@Usuario] [--self] [--guild] [--url] [--size=256]"
        )

    async def run(self, message, args, flags):
        target = None

        if 'self' in flags:
            assert message.author

            target = message.author
        elif 'guild' in flags:
            assert message.guild

            target = message.guild
        else:
            mentions = flags['mentions']
            target = mentions[0] if mentions else None
        
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

        icon_url = str(target.avatar_url_as(size=size) if isinstance(target, discord.User) else target.icon_url_as(size=size))

        if "url" in flags:
            return icon_url
        
        out = self.create_response_embed(message) 
        out.set_image(url=icon_url)
            
        if isinstance(target, discord.Member):
            out.title = f"Avatar de {target.name}"
        
        return out

class CRemind(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            enable_usermap = True,
            name = "remind",
            aliases = ['re'],
            description = "Registra um determinado lembrete de acordo com o tempo de espera `--time` informado.",
            usage = "--time=1h30m [--list] [--remove=ID] [--clear] [lembrete...]"
        )

        self.limit = 3

    async def run(self, message, args, flags):
        assert message.author

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

                return ReactionType.SUCCESS
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
                t = TimeoutContext(
                    seconds, 
                    self.callable_send_reminder, 
                    callback=self.callable_free_reminder, 
                    ctx=message, 
                    text=text if text else f"Lembrete sem título",
                    timestamp=time.time()
                )

                stored.append(t)
                t.create_task()

                return ReactionType.SUCCESS
            else:
                raise CommandError(f"Você atingiu o limite de {self.limit} lembretes registrados, por favor tente mais tarde.")
        
    async def callable_send_reminder(self, reminder, kwargs):
        ctx = kwargs['ctx']
        text = kwargs.get('text', None)

        await ctx.author.send(f":bell: Olá <@{ctx.author.id}>, estou te avisando sobre um **lembrete**!" if not text else f":bell: Olá <@{ctx.author.id}>, estou te avisando sobre:\n\n{text}")

    async def callable_free_reminder(self, reminder, kwargs):
        ctx = kwargs['ctx']

        stored = self.get_user_storage(ctx.author)
        assert stored

        try:
            stored.remove(reminder)
        except ValueError:
            logging.error(f"callback_free_reminder > Failed to remove {type(reminder)} from storage, context = {reminder}")

class CSpotify(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "spotify",
            aliases = ['sptfy'],
            description = "Retorna informações da atividade Spotify que o usuário esteja realizando.",
            usage = "@Usuario"
        )

    async def run(self, message, args, flags):
        mentions = flags['mentions']

        target = mentions[0] if mentions else None

        if not target:
            return self.get_usage_embed(message)

        spotify = None

        for act in target.activities:
            if isinstance(act, discord.Spotify):
                spotify = act

        if spotify:
            out = self.create_response_embed(message) 
            out.title = f"{target.name} está ouvindo"
            out.add_field(name='Título', value=spotify.title, inline=True)
            out.add_field(name='Artista(s)', value=', '.join(spotify.artists), inline=True)
            out.add_field(name='Album', value=spotify.album, inline=True)
            out.add_field(name='Duração', value=seconds_string(spotify.duration.total_seconds()), inline=True)
            out.color = spotify.color
            out.set_thumbnail(url=spotify.album_cover_url)
            return out
        else:
            return ':information_source: O usuário não está no Spotify atualmente.'

class CEmbed(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "embed",
            aliases = ['emb'],
            description = "Retorna um Embed de acordo com os parâmetros informados.",
            usage = '[-t "titulo"] [-d "descricao"] [-img "url"] [-timg "url"]'
        )

    async def run(self, message, args, flags):
        if not args or not flags:
            return self.get_usage_embed(message)

        embed = self.create_response_embed(message)
        index = 0

        for key in flags.keys():
            if index < len(args):
                curritem = args[index]

                if key == 't':
                    embed.title = curritem
                elif key == 'd':
                    embed.description = curritem
                elif key == 'img':
                    embed.set_image(url=curritem)
                elif key == 'timg':
                    embed.set_thumbnail(url=curritem)

                index += 1
            else:
                break

        return embed