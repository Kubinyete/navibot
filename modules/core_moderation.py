from navibot.client import BotCommand, PermissionLevel
from navibot.errors import CommandError

class CNsfw(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'nsfw',
            description = "Ativa ou desativa o conteúdo NSFW para esta Guild.",
            usage = "{name} [-e|--enable] [-d|--disable]",
            permissionlevel=PermissionLevel.GUILD_MOD
        )

    async def run(self, message, args, flags):
        gsm = self.get_guild_settings_manager()
        var = await gsm.get_guild_variable(message.channel.guild.id, 'nsfw_disabled')

        if var:
            if 'enable' in flags or 'e' in flags: 
                var.set_value(False)
            elif 'disable' in flags or 'd' in flags:
                var.set_value(True)
            else:
                return f"Conteúdo NSFW está atualmente **{'desabilitado' if var.get_value() else 'habilitado'}** para esta Guild."

            await gsm.update_guild_variable(var)
            await message.add_reaction('✅')
        else:
            raise CommandError('Variável `nsfw_disabled` não encontrado no contexto da Guild atual.')