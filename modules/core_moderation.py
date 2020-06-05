import asyncio
import logging
import discord

from navibot.client import BotCommand, BotContext, EmojiType, PermissionLevel, ClientEvent, Plugin
from navibot.parser import CommandParser
from navibot.errors import CommandError

class PWelcomeMessage(Plugin):
    async def on_plugin_load(self):
        self.bind_event(
            ClientEvent.MEMBER_JOIN,
            self.callable_receive_member_join
        )

    async def callable_receive_member_join(self, kwargs):
        member = kwargs.get('member')

        vc, vm = await asyncio.gather(
            self.bot.guildsettings.get_guild_variable(member.guild.id, 'gst_welcome_channel_id'),
            self.bot.guildsettings.get_guild_variable(member.guild.id, 'gst_welcome_channel_message')
        )

        if vc and vc.get_value() and vm and vm.get_value():
            channel = member.guild.get_channel(vc.get_value())

            if channel:
                await self.bot.handle_command_parse(
                    BotContext(
                        self.bot,
                        channel,
                        member
                    ),
                    vm.get_value()
                )

class CNsfw(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'nsfw',
            description = "Ativa ou desativa o conteúdo NSFW para esta Guild.",
            usage = "[-e|--enable] [-d|--disable]",
            permissionlevel=PermissionLevel.GUILD_ADMIN
        )

    async def run(self, ctx, args, flags):
        var = await self.bot.guildsettings.get_guild_variable(ctx.channel.guild.id, 'nsfw_disabled')

        if var:
            if 'enable' in flags or 'e' in flags: 
                var.set_value(False)
            elif 'disable' in flags or 'd' in flags:
                var.set_value(True)
            else:
                return f"Conteúdo NSFW está atualmente **{'desabilitado' if var.get_value() else 'habilitado'}** para esta Guild."

            if await self.bot.guildsettings.update_guild_variable(var):
                return EmojiType.CHECK_MARK
            else:
                return EmojiType.CROSS_MARK
        else:
            raise CommandError('Variável `nsfw_disabled` não encontrado no contexto da Guild atual.')

class CSetWelcomeChannel(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'setwelcomechannel',
            description = "Configura um canal para ser utilizado como canal de boas-vindas toda vez que um membro novo entrar na Guild, a mensagem pode ser customizada através do comando `setwelcomemessage`.",
            usage = "#Channel [-d|--disable]",
            permissionlevel=PermissionLevel.GUILD_MOD
        )

    async def run(self, ctx, args, flags):
        channel = flags.get('channel_mentions', None)
        
        if channel:
            channel = channel[0]

        if not channel and (not 'disable' in flags and not 'd' in flags): 
            return self.get_usage_embed(ctx)

        var = await self.bot.guildsettings.get_guild_variable(ctx.channel.guild.id, 'gst_welcome_channel_id')

        if var:
            if 'disable' in flags or 'd' in flags:
                var.set_value(0)
            else:
                var.set_value(channel.id)

            if await self.bot.guildsettings.update_guild_variable(var):
                return EmojiType.CHECK_MARK
            else:
                return EmojiType.CROSS_MARK
        else:
            raise CommandError('Variável `gst_welcome_channel_id` não encontrado no contexto da Guild atual.')

class CSetWelcomeMessage(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'setwelcomemessage',
            description = "Configura um comando para ser executado toda vez que um membro novo entrar na Guild atual, por favor veja `help --syntax` antes de tentar trocá-la.",
            usage = "[comando...]",
            permissionlevel=PermissionLevel.GUILD_MOD
        )

    async def run(self, ctx, args, flags):
        if not args: 
            return self.get_usage_embed(ctx)

        var = await self.bot.guildsettings.get_guild_variable(ctx.channel.guild.id, 'gst_welcome_channel_message')

        if var:
            cmd = ' '.join(args)

            var.set_value(cmd)

            if await self.bot.guildsettings.update_guild_variable(var):
                return EmojiType.CHECK_MARK
            else:
                return EmojiType.CROSS_MARK
        else:
            raise CommandError('Variável `gst_welcome_channel_message` não encontrado no contexto da Guild atual.')

class CSimulateMemberJoin(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "simulatememberjoin",
            description = "Simula um evento on_member_join na Guild atual, utilizando o autor deste comando como parâmetro.",
            permissionlevel = PermissionLevel.GUILD_MOD,
            hidden = True
        )

    async def run(self, ctx, args, flags):
        # @NOTE:
        # Isso aqui é temporário, não faz sentido ativar um evento de MEMBER_JOIN inteiro só para testar o comando de boas-vindas
        await self.bot.client.dispatch_event(
            ClientEvent.MEMBER_JOIN,
            member=ctx.author
        )
        
class CSetPrefix(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'setprefix',
            description = "Altera o prefixo de ativação do bot no contexto da Guild atual.",
            usage = "prefixo [-r|--reset]",
            permissionlevel=PermissionLevel.GUILD_ADMIN
        )

    async def run(self, ctx, args, flags):
        if not args or len(args[0]) < 1:
            return self.get_usage_embed(ctx)

        var = await self.bot.guildsettings.get_guild_variable(ctx.channel.guild.id, 'bot_prefix')

        if var:
            var.set_value(args[0])

            if await self.bot.guildsettings.update_guild_variable(var):
                return EmojiType.CHECK_MARK
            else:
                return EmojiType.CROSS_MARK
        else:
            raise CommandError('Variável `bot_prefix` não encontrado no contexto da Guild atual.')