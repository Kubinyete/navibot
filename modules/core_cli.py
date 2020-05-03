import logging
from navibot.client import CliCommand
from navibot.errors import CommandError

class CEcho(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'echo'
        )

    async def run(self, ctx, args, flags):
        return args

class CHelp(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'help'
        )
    
    async def run(self, ctx, args, flags):
        return [f'{c.name}' for c in self.bot.clicommands.get_all_commands()]

class CReload(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'reload'
        )

    async def run(self, ctx, args, flags):
        #try:
        await self.bot.reload_all_modules()
        return 'Todos os modulos foram recarregados.'
        #except Exception as e:
        #    raise CommandError(f'Ocorreu um erro ao tentar realizar o reload:\n\n{type(e).__name__}: {e}')

class CHooks(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'hooks'
        )

    async def run(self, ctx, args, flags):
        return [str(h) for h in self.bot.hooks.hooks]