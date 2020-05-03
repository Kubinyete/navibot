import logging
from navibot.client import CliCommand
from navibot.errors import CommandError

class CEcho(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'echo',
            aliases = ['ec'],
            usage = '[texto...]'
        )

    async def run(self, ctx, args, flags):
        return args

class CHelp(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'help',
            aliases = ['h']
        )
    
    async def run(self, ctx, args, flags):
        return [f'{c.name}' for c in self.bot.clicommands.get_all_commands()]

class CReload(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'reload',
            aliases = ['rl']
        )

    async def run(self, ctx, args, flags):
        try:
            await self.bot.reload_all_modules()
            return 'Todos os modulos foram recarregados.'
        except Exception as e:
            raise CommandError(f'Ocorreu um erro ao tentar realizar o reload:\n\n{type(e).__name__}: {e}')

class CSetContext(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'setcontext',
            aliases = ['ctx'],
            usage = 'id [-u|--user] [-c|--channel]'
        )

    async def run(self, ctx, args, flags):
        if not args:
            return self.get_usage_text()

        try:
            target_id = int(args[0])
        except ValueError:
            raise CommandError('O ID informado não é um número válido.')

        if 'u' in flags or 'user' in flags:
            # @NOTE:
            # Estamos usando o BotContext.author como se fosse um target user e não como um author realmente...
            # Isso semânticamente está meio errado, porém, no contexto de um comando CLI, quem é o autor dos comandos é sempre a outra ponta da conexão
            # Então assumir que exista um autor de objeto aqui não faria sentido também.
            target = self.bot.client.get_user(target_id)

            if not target:
                raise CommandError(f'O usuário {target_id} não foi encontrado.')
            else:
                ctx.update_bot_context(
                    target
                )
        elif 'c' in flags or 'channel' in flags:
            target = self.bot.client.get_channel(target_id)

            if not target:
                raise CommandError(f'O canal {target_id} não foi encontrado.')
            else:
                ctx.update_bot_context(
                    target
                )
        else:
            return self.get_usage_text()

        return 'O contexto dos comandos foi alterado!'
        
class CSay(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'say',
            aliases = ['s'],
            usage = '[texto...]'
        )

    async def run(self, ctx, args, flags):
        try:
            await ctx.say(args)
        except Exception as e:
            raise CommandError(f'Ocorreu um erro ao tentar responder o contexto atual:\n\n{type(e).__name__}: {e}')
