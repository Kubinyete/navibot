import navibot
from libs.yandere import YandereApi

class CYandere(navibot.BotCommand):
    def initialize(self):
        self.name = "yandere"
        self.aliases = ['yan']
        self.description = "Exibe um Slider de uma ou mais imagens retornadas pela API do site yande.re de acordo com as tags informadas por argumento."
        self.usage = f"{self.name} [tag1] [tagN]..."

        self.api = YandereApi()

    async def run(self, message, args, flags):
        raise NotImplementedError()