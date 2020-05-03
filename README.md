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

Isso permite que até os comandos mais básicos do bot sejam utilizados para formarem outros comandos, como é o caso dos "comandos interpretados" carregados durante a inicialização (a forma com que esses comandos são carregados pode estar sujeito a mudanças no futuro).

```json
{
    "interpreted_commands": [
        {
            "name": "ayaya", 
            "value": "embed -img \"{choice https://cdn.frankerfacez.com/emoticon/162146/4 https://cdn.frankerfacez.com/emoticon/250475/4 https://i.imgur.com/jS7AgX5.gif}\" -t AYAYA -d \"{getarg --all}\""
        },
        {
            "name": "rainbowpls", 
            "value": "embed -img \"{choice https://i.imgur.com/WYVUg98.gif https://i.imgur.com/XWvZihi.gif}\" -t RainbowPls -d \"{getarg --all}\""
        },
        {
            "name": "chikapls", "
            value": "embed -img \"{choice https://i.imgur.com/7mRPZXg.gif https://i.imgur.com/gQMkb2L.gif https://i.imgur.com/8URcIR1.gif}\" -t chikaPls -d \"{getarg --all}\""
        }
    ]
}
```

Adicionalmente, é possível registrar "ganchos" que são carregados e registram-se em eventos do cliente, como é o caso deste ModuleHook que fica responsável por receber os membros que recentemente entraram em uma Guild, e processar, de acordo com o contexto da Guild, a mensagem de boas-vindas configurada pela Guild (que neste caso, assumimos também que seja um comando).

```py
# modules/core_moderation.py
class HWelcomeMessage(ModuleHook):
    async def callable_receive_member_join(self, kwargs):
        member = kwargs.get('member')

        gsm = self.get_guild_settings_manager()

        vc = await gsm.get_guild_variable(member.guild.id, 'gst_welcome_channel_id')
        vm = await gsm.get_guild_variable(member.guild.id, 'gst_welcome_channel_message')

        if vc and vc.get_value() and vm and vm.get_value():
            channel = member.guild.get_channel(vc.get_value())

            if channel:
                await self.bot.handle_command_parse(
                    Context(
                        self.bot,
                        channel,
                        member.guild,
                        member
                    ),
                    vm.get_value()
                )
    
    def run(self):
        self.bind_event(
            'member_join',
            self.callable_receive_member_join
        )
```

O resultado deste ModuleHook, após o processamento do comando de boas-vindas específicado pelo moderador da Guild, temos a seguinte mensagem:

![Mensagem de boas-vindas](https://raw.githubusercontent.com/Kubinyete/navibot/dev/repo/doc/welcome-message.png)

Com isso, podemos assumir no futuro que vamos ter situações em que cada Guild poderá customizar inclusive seus próprios comandos.