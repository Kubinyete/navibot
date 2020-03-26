# NaviBot

**NaviBot** é um bot **experimental** escrito utilizando a biblioteca [discord.py](https://github.com/Rapptz/discord.py) por razões de aprendizado, mais específicamente para experimentar com o asyncio e também conseguir construir e replicar algumas funcionalidades que já vi serem implementadas.

# Comandos

Os comandos são automaticamente carregados a partir do diretório `./modules/`, sendo que cada script presente é carregado e todas as classes herdadas de `navibot.client.BotCommand` são carregadas durante a inicialização do bot.

# Criando o primeiro comando

Comando de exemplo do "framework" atualmente presente:

```py
# modules/helloworld.py
from navibot.client import BotCommand

class CHelloworld(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'helloworld',
            aliases = ['hw'],
            description = "Exibe um olá mundo!."
        )

    async def run(self, message, args, flags):
        return 'Olá mundo!'
```
