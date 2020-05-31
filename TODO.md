# TODO

#### Navibot

- [x] make-config.sh (2020-04-14 11:24:48)
- [X] Adicionar operador que desativa a resolução de subcomandos dentro de argumentos literais. (2020-04-15 21:00:50)
- [X] Adicionar suporte à CLI (se conectando ao bot, podendo executar comandos, interagir com a instância e podendo receber as mensagens dos canais) (2020-05-04 22:42:48)
- [ ] Suporte a mais de uma linguagem (pt-br, en, etc...)
- [ ] Launcher separado estilo daemon para o bot.

#### Comandos

- [X] hotreload (2020-04-19 00:10:08)
- [X] setprefix prefixo [-r|--reset] (2020-04-15 21:01:03)
    - [X] Fallback, mencionar o bot para saber o prefixo atual (2020-04-15 21:01:32)
    - [X] Fallback, mencionar o bot para resetar o prefixo (2020-04-15 21:01:34)

- [X] github (interpretado) (2020-05-05 23:23:13)
    - [X] O bot deve dizer o URL do github e deixar com que o próprio cliente resolva o embed (desativar comportamento automatico do BotContext.reply() de enviar somente embeds)

- [X] coinflip (interpretado) (2020-05-05 23:23:16)
- [X] regexp (2020-05-12 01:06:51) findall
- [X] base64 (2020-05-12 01:11:08) encode/decode
- [X] md5 (2020-05-12 01:26:55) hexdigest
- [X] pat @Usuario
- [X] triggered [@Usuario] [URL] [Attachment] (2020-05-12 14:34:10)
- [X] think [@Usuario] [URL] [Attachment] (2020-05-15 23:45:33)
- [ ] textimage [texto...]

#### Comandos - Low Priority

- [ ] help [cmd] [--syntax]

- [ ] scared (interpretado)
- [ ] hug @Usuario

- [ ] asciify [@Usuario] [URL] [Attachment]

#### Comandos - DB Interactivity

- [ ] marry @Usuario
- [ ] divorce @Usuario

- [ ] profile [@Usuario]
    Um perfil deve ser vinculado somente à uma Guild, ou deve ser global?
        Vamos inicialmente testar um perfil para cada Guild, pois ai podemos customizar a experiência do perfil para cada Guild.
    Suporte à imagens de fundo (capa de perfil)?
        Sim. Limite max. de 128 KB por membro, o bot fica responsável pela diminuição da imagem (geração de versão de miniatura).
        Lembrete: Limite de uma imagem attachment é 400x300.
        Suporte a links de outras contas? Faz mais sentido para links de coisas não tão mainstream (Ex: Osu)
            Osu, Steam, Twitter, Facebook?
    NOTE: Não consegui implementar isso de forma fácil, tive problemas com o MySQL, troquei a biblioteca para o aiomysql e usando pool de conexão, mas mesmo assim há conflitos de transações entre os updates no EXP do usuário... O modulo opt_progression foi desativado por enquanto.
- [ ] credits [@Usuario]
- [ ] exp [@Usuario]
- [ ] givecredits amount [@Usuario]
- [ ] giveexp amount [@Usuario]

- [ ] shop [buy|search|show] [itemName]

- [ ] reactionroles reactionRoleId reaction @Role [--list] [--remove-messages] [--make]
    Pensar melhor nisso aqui, como resolver a questão de limpar roles e a mensagem que da os roles, etc...