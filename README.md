# Navibot

**Navibot** é um bot **experimental** escrito utilizando a biblioteca [discord.py](https://github.com/Rapptz/discord.py) por razões de aprendizado, mais específicamente para experimentar com o asyncio e também conseguir construir e replicar algumas funcionalidades que já vi serem implementadas.

# Comandos

Os comandos são automaticamente carregados a partir do diretório `./modules/`, sendo que cada script presente é carregado e todas as classes herdadas de `navibot.client.BotCommand` são carregadas durante a inicialização do bot.

# Criando o primeiro comando

Exemplos de comandos:

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

    async def run(self, ctx, args, flags):
        # Você não é obrigado a retornar as respostas, mas facilita a leitura.
        # Ex:
        # await ctx.reply("Teste 123")
        
        return 'Olá mundo!'
```

O grande diferencial deste bot, é a implementação de um operador PIPE (|) e a possibilidade de utilizar o retorno de comandos como argumento para outros comandos (operadores { e } encontrado dentro de strings literais).

![Operador PIPE](https://raw.githubusercontent.com/Kubinyete/navibot/dev/repo/doc/operador-pipe.png)

Adicionalmente, é possível registrar "ganchos" que são carregados e registram-se em eventos do cliente, como é o caso deste ModuleHook que fica responsável por receber os membros que recentemente entraram em uma Guild, e processar, de acordo com o contexto da Guild, a mensagem de boas-vindas configurada pela Guild (que neste caso, assumimos também que seja um comando).

```py
# modules/core_moderation.py
class HWelcomeMessage(ModuleHook):
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
                        member.guild,
                        member
                    ),
                    vm.get_value()
                )
    
    def run(self):
        self.bind_event(
            ClientEvent.MEMBER_JOIN,
            self.callable_receive_member_join
        )
```

O resultado deste ModuleHook, após o processamento do comando de boas-vindas específicado pelo moderador da Guild, temos a seguinte mensagem:

![Mensagem de boas-vindas](https://raw.githubusercontent.com/Kubinyete/navibot/dev/repo/doc/welcome-message.png)

Com isso, podemos assumir no futuro que vamos ter situações em que cada Guild poderá customizar inclusive seus próprios comandos.