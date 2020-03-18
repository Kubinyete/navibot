# NaviBot

**NaviBot** é um bot **experimental** escrito utilizando a biblioteca [discord.py](https://github.com/Rapptz/discord.py) por razões de aprendizado, mais específicamente para experimentar com o asyncio e também conseguir construir e replicar algumas funcionalidades que já vi serem implementadas.

# Comandos

Os comandos são automaticamente carregados a partir do diretório `./modules/`, sendo que cada script presente é carregado e todas as classes herdadas de `navibot.BotCommand` são carregadas durante a inicialização do bot.

# Criando o primeiro comando

Comando de exemplo do "framework" atualmente presente:

```py
# modules/mymodule.py
import navibot

# O nome da classe não precisa ser exatamente desta forma, é apenas um formato que este repo segue.
class CHelloworld(navibot.BotCommand):
    def initialize(self):
        self.name = 'helloworld'                        # Se não especificado, atribuirá o proprio nome da classe (chelloworld).
        self.aliases = ['hw']                           # Define uma lista de apelidos para este comando (preencherá a tabela de comandos).
        self.description = "Exibe um helloworld."       # Descrição a ser informada ao usuário ao requisitar o uso do comando.
        self.usage = f"{self.name}"                     # String técnica demonstrando o uso do comando, não existe exatamente um padrão até o momento.

    async def run(self, message, args, flags):
        # Retornar uma str fará com que o bot envie essa mensagem através de um Embed (comportamento padrão).
        # Já que estamos utilizando a discord.py, o próprio comando pode enviar suas mensagem, sem precisar dar return, porém é recomendado (organização).
        return "Hello world!"
```
