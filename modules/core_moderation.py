import logging

from navibot.client import BotCommand, ReactionType, PermissionLevel
from navibot.parser import CommandParser
from navibot.errors import CommandError

class CNsfw(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'nsfw',
            description = "Ativa ou desativa o conteúdo NSFW para esta Guild.",
            usage = "[-e|--enable] [-d|--disable]",
            permissionlevel=PermissionLevel.GUILD_MOD
        )

    async def run(self, message, args, flags):
        gsm = self.get_guild_settings_manager()
        var = await gsm.get_guild_variable(message.guild.id, 'nsfw_disabled')

        if var:
            if 'enable' in flags or 'e' in flags: 
                var.set_value(False)
            elif 'disable' in flags or 'd' in flags:
                var.set_value(True)
            else:
                return f"Conteúdo NSFW está atualmente **{'desabilitado' if var.get_value() else 'habilitado'}** para esta Guild."

            await gsm.update_guild_variable(var)
            return ReactionType.SUCCESS
        else:
            raise CommandError('Variável `nsfw_disabled` não encontrado no contexto da Guild atual.')

class CSetWelcomeChannel(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'setwelcomechannel',
            description = "Configura um canal para ser utilizado como canal de boas-vindas toda vez que um membro novo entrar na Guild.",
            usage = "#Channel [-d|--disable]",
            permissionlevel=PermissionLevel.GUILD_MOD
        )

    async def run(self, message, args, flags):
        assert message.guild

        channel = flags.get('channel_mentions', None)
        
        if channel:
            channel = channel[0]

        if not channel and (not 'disable' in flags and not 'd' in flags): 
            return self.get_usage_embed(message)

        gsm = self.get_guild_settings_manager()
        var = await gsm.get_guild_variable(message.guild.id, 'gst_welcome_channel_id')

        if var:
            if 'disable' in flags or 'd' in flags:
                var.set_value(0)
            else:
                var.set_value(channel.id)

            if await gsm.update_guild_variable(var):
                return ReactionType.SUCCESS
            else:
                return ReactionType.FAILURE
        else:
            raise CommandError('Variável `gst_welcome_channel_id` não encontrado no contexto da Guild atual.')

class CSetWelcomeMessage(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'setwelcomemessage',
            description = "Configura um comando para ser executado toda vez que um membro novo entrar na Guild atual.",
            usage = "[comando...]",
            permissionlevel=PermissionLevel.GUILD_MOD
        )

    async def run(self, message, args, flags):
        assert message.guild

        if not args: 
            return self.get_usage_embed(message)

        gsm = self.get_guild_settings_manager()
        var = await gsm.get_guild_variable(message.guild.id, 'gst_welcome_channel_message')

        if not var:
            raise CommandError('Variável `gst_welcome_channel_message` não encontrado no contexto da Guild atual.')
        else:
            cmd = ' '.join(args)
            
            try:
                CommandParser(cmd).parse()
            except Exception as e:
                logging.error(e)
                raise CommandError(f'Ocorreu um erro ao tentar adicionar o comando interpretado:\n{e}')

            var.set_value(cmd)

            if await gsm.update_guild_variable(var):
                return ReactionType.SUCCESS
            else:
                return ReactionType.FAILURE
