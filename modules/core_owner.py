import discord
import asyncio
import logging
import aiohttp

from navibot.client import BotCommand, InterpretedCommand, PermissionLevel, ReactionType
from navibot.parser import CommandParser
from navibot.errors import CommandError

class CSetAvatar(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "setavatar",
            description = "Edita o perfil do bot atual, recebe um URL da imagem nova de perfil, a qual será baixada e enviada.",
            usage = "URL",
            permissionlevel = PermissionLevel.BOT_OWNER
        )

        self.httpsession = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60)
        )

        self.discord_edit_timeout = 30

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        avatar_url = ' '.join(args)
        avatar_bytes = None

        try:
            async with self.httpsession.get(avatar_url) as resp:
                if resp.status == 200:
                    avatar_bytes = await resp.read()
                else:
                    raise CommandError("Não foi possível obter o novo avatar através da URL fornecida, o destino não retornou OK.")
        except aiohttp.ClientError as e:
            logging.exception(f'CSETAVATAR: {type(e).__name__}: {e}')
            raise CommandError("Não foi possível obter o novo avatar através da URL fornecida.")

        try:
            # user.edit() pode travar caso ultrapassarmos o limite e ficarmos de cooldown ou se o upload estiver demorando muito (não seria comum neste caso).
            await asyncio.wait_for(
                self.bot.client.user.edit(
                    avatar=avatar_bytes
                ), self.discord_edit_timeout
            )
        except discord.InvalidArgument as e:
            logging.exception(f'CSETAVATAR: {type(e).__name__}: {e}')
            raise CommandError("O formato de imagem fornecido não é suportado pelo Discord, favor informar os formatos (JPEG, PNG).")
        except discord.HTTPException as e:
            logging.exception(f'CSETAVATAR: {type(e).__name__}: {e}')
            raise CommandError("Não foi possível editar o perfil do bot.")
        except asyncio.TimeoutError as e:
            logging.exception(f'CSETAVATAR: {type(e).__name__}: {e}')
            raise CommandError("Não foi possível editar o perfil do bot, o tempo limite de envio foi excedido.")
            
        return ReactionType.SUCCESS

class CSetName(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "setname",
            description = "Edita o perfil do bot atual, recebe um novo nome de usuário.",
            usage = "[nome...]",
            permissionlevel = PermissionLevel.BOT_OWNER
        )

        self.discord_edit_timeout = 10

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        username = ' '.join(args)

        try:
            # user.edit() pode travar caso ultrapassarmos o limite e ficarmos de cooldown.
            await asyncio.wait_for(
                self.bot.client.user.edit(
                    username=username
                ), self.discord_edit_timeout
            )
        except (discord.InvalidArgument, discord.HTTPException, asyncio.TimeoutError) as e:
            logging.exception(f'CSETNAME: {type(e).__name__}: {e}')
            raise CommandError("Não foi possível editar o perfil do bot.")
            
        return ReactionType.SUCCESS

class CGuildVariables(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'guildvariable',
            aliases = ['var', 'gvar'],
            description = "Gerencia as variáveis da Guild atual.",
            usage = "variavel [novo valor] [--list]",
            permissionlevel=PermissionLevel.BOT_OWNER
        )

    async def run(self, message, args, flags):
        gsm = self.get_guild_settings_manager()
        gvars = await gsm.get_all_guild_variables(message.guild.id)

        if 'list' in flags:
            text = ''
            for key, value in gvars.items():
                text += f'**{value.valuetype.name.lower()}**:`{key}` = `{value.value}`\n'

            return text
        else:
            if not args:
                return self.get_usage_embed(message)

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
                    raise CommandError(f'A variável `{args[0]}` não recebeu um tipo de dados coerente, **{expected_variable.valuetype.name.lower()}** esperado.')

                try:
                    if await gsm.update_guild_variable(expected_variable):
                        return ReactionType.SUCCESS
                    else:
                        expected_variable.set_value(prev_value)
                    
                        return ReactionType.FAILURE
                except Exception as e:
                    logging.exception(f'CGUILDVARIABLES: {type(e).__name__}: {e}')
                    
                    expected_variable.set_value(prev_value)
                    
                    return ReactionType.FAILURE
            else:
                # Sem formatação, pois podemos utilizar o valor da variável em outros comandos
                # return f'**{expected_variable.valuetype.name.lower()}**:`{expected_variable.key}` = `{expected_variable.value}`\n'
                
                return expected_variable.get_value()

class CAddCommand(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "addcommand",
            description = "Adiciona um comando interpretado.",
            usage = 'nome [comando...]',
            permissionlevel = PermissionLevel.BOT_OWNER
        )

    async def run(self, message, args, flags):
        if len(args) < 2:
            return self.get_usage_embed(message)

        cmd = ' '.join(args[1:])

        try:    
            self.bot.add_interpreted_command(
                InterpretedCommand(
                    self.bot,
                    args[0],
                    cmd
                )
            )

            return ReactionType.SUCCESS
        except Exception as e:
            logging.exception(f'CADDCOMMAND: {type(e).__name__}: {e}')

            raise CommandError(f'Ocorreu um erro ao tentar adicionar o comando interpretado:\n\n`{e}`')

class CRemoveCommand(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "removecommand",
            description = "Remove um comando interpretado.",
            usage = 'nome',
            permissionlevel = PermissionLevel.BOT_OWNER
        )

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        try:
            self.bot.remove_interpreted_command(args[0])
            
            return ReactionType.SUCCESS
        except Exception as e:
            logging.exception(f'CREMOVECOMMAND: {type(e).__name__}: {e}')
            raise CommandError(f'Ocorreu um erro ao tentar remover o comando interpretado:\n\n`{e}`')