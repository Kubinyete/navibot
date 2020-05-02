import logging

from navibot.client import CliCommand
from navibot.errors import CommandError

class CEcho(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'echo',
        )

    async def run(self, ctx, args, flags):
        return args

class CSelect(CliCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'select',
        )

    async def run(self, ctx, args, flags):
        pass
        