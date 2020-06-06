import discord
import asyncio
import logging
import aiohttp
import io
import math
import PIL.Image
import PIL.ImageFont
import PIL.ImageDraw

from navibot.client import BotCommand, InterpretedCommand, PermissionLevel, EmojiType
from navibot.errors import CommandError

class CSetAvatar(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "setavatar",
            description = "Edita o perfil do bot atual, recebe um URL da imagem nova de perfil, a qual será baixada e enviada.",
            usage = "URL",
            permissionlevel = PermissionLevel.BOT_OWNER,
            hidden = True
        )

        # 5 MB
        self.http_max_file_size = 5 * 1024 * 1024
        self.discord_edit_timeout = 30

    async def run(self, ctx, args, flags):
        if not args:
            return self.get_usage_embed(ctx)

        avatar_url = args[0]
        avatar_bytes = await self.get_file_from_url(avatar_url, max_size=self.http_max_file_size)

        try:
            # user.edit() pode travar caso ultrapassarmos o limite e ficarmos de cooldown ou se o upload estiver demorando muito (não seria comum neste caso).
            await asyncio.wait_for(
                self.bot.client.user.edit(
                    avatar=avatar_bytes.getvalue()
                ), self.discord_edit_timeout
            )
        except (discord.InvalidArgument, discord.HTTPException, asyncio.TimeoutError):
            raise CommandError("Não foi possível editar o perfil do bot.")
            
        return EmojiType.CHECK_MARK

class CSetName(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "setname",
            description = "Edita o perfil do bot atual, recebe um novo nome de usuário.",
            usage = "[nome...]",
            permissionlevel = PermissionLevel.BOT_OWNER,
            hidden = True
        )

        self.discord_edit_timeout = 10

    async def run(self, ctx, args, flags):
        if not args:
            return self.get_usage_embed(ctx)

        username = ' '.join(args)

        try:
            # user.edit() pode travar caso ultrapassarmos o limite e ficarmos de cooldown.
            await asyncio.wait_for(
                self.bot.client.user.edit(
                    username=username
                ), self.discord_edit_timeout
            )
        except (discord.InvalidArgument, discord.HTTPException, asyncio.TimeoutError):
            raise CommandError("Não foi possível editar o perfil do bot.")
            
        return EmojiType.CHECK_MARK

class CGuildVariables(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'guildvariable',
            aliases = ['var', 'gvar'],
            description = "Gerencia as variáveis da Guild atual.",
            usage = "variavel [novo valor] [--list] [--reset]",
            permissionlevel=PermissionLevel.BOT_OWNER,
            hidden = True
        )

    async def run(self, ctx, args, flags):
        gvars = await self.bot.guildsettings.get_all_guild_variables(ctx.channel.guild.id)

        if 'list' in flags:
            text = ''
            for key, value in gvars.items():
                text += f'**{value.valuetype.name.lower()}**:`{key}` = `{value.value}`\n'

            return text
        else:
            if not args:
                return self.get_usage_embed(ctx)

            try:
                expected_variable = gvars[args[0]]
            except KeyError:
                raise CommandError(f'A variável `{args[0]}` não existe no contexto da Guild atual.')

            if 'reset' in flags:
                if await self.bot.guildsettings.remove_guild_variable(expected_variable):
                    return EmojiType.CHECK_MARK
                else:
                    return EmojiType.CROSS_MARK
            else:
                if len(args) > 1:
                    new_value = ' '.join(args[1:])
                    prev_value = expected_variable.get_value()

                    try:
                        expected_variable.set_value(new_value)
                    except ValueError:
                        raise CommandError(f'A variável `{args[0]}` não recebeu um tipo de dados coerente, **{expected_variable.valuetype.name.lower()}** esperado.')

                    if await self.bot.guildsettings.update_guild_variable(expected_variable):
                        return EmojiType.CHECK_MARK
                    else:
                        expected_variable.set_value(prev_value)
                        return EmojiType.CROSS_MARK
                else:
                    return str(expected_variable.get_value())

class CAddCommand(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "addcommand",
            description = "Adiciona um comando interpretado.",
            usage = 'nome [comando...]',
            permissionlevel = PermissionLevel.BOT_OWNER,
            hidden = True
        )

    async def run(self, ctx, args, flags):
        if len(args) < 2:
            return self.get_usage_embed(ctx)

        cmd = ' '.join(args[1:])

        try:    
            self.bot.commands.add_interpreted_command(
                InterpretedCommand(
                    self.bot,
                    cmd,
                    name = args[0]
                )
            )

            return EmojiType.CHECK_MARK
        except Exception as e:
            raise CommandError(f'Ocorreu um erro ao tentar adicionar o comando interpretado:\n\n`{e}`')

class CRemoveCommand(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "removecommand",
            description = "Remove um comando interpretado.",
            usage = 'nome',
            permissionlevel = PermissionLevel.BOT_OWNER,
            hidden = True
        )

    async def run(self, ctx, args, flags):
        if not args:
            return self.get_usage_embed(ctx)

        try:
            self.bot.commands.remove_interpreted_command(args[0])
            
            return EmojiType.CHECK_MARK
        except Exception as e:
            raise CommandError(f'Ocorreu um erro ao tentar remover o comando interpretado:\n\n`{e}`')

class CReload(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "reload",
            description = "Efetua a reinicialização de todos os comandos e o processo de inicialização, consequentemente, carregando novamente os comandos.",
            permissionlevel = PermissionLevel.BOT_OWNER,
            hidden = True
        )

    async def run(self, ctx, args, flags):
        try:
            await self.bot.reload_all_modules()
            
            return EmojiType.CHECK_MARK
        except Exception as e:
            raise CommandError(f'Ocorreu um erro ao tentar efetuar o reload:\n\n`{type(e).__name__}: {e}`')