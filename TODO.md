# TODO

#### Navibot

- [x] make-config.sh (2020-04-14 11:24:48)
- [X] Adicionar operador que desativa a resolução de subcomandos dentro de argumentos literais. (2020-04-15 21:00:50)
- [X] Adicionar suporte à CLI (se conectando ao bot, podendo executar comandos, interagir com a instância e podendo receber as mensagens dos canais) (2020-05-04 22:42:48)
- [X] Launcher separado estilo daemon para o bot.
- [ ] Suporte a mais de uma linguagem (pt-br, en, etc...)

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

- [X] profile [@Usuario]
    - [X] Monitorar e atribuir EXP para os membros
    - [X] Permitir visualizar uma assinatura de perfil
    - [X] Suporte a troca de fundo
        
- [ ] credits [@Usuario]
- [ ] exp [@Usuario]
- [ ] givecredits amount [@Usuario]
- [ ] giveexp amount [@Usuario]

- [ ] shop [buy|search|show] [itemName]

- [ ] reactionroles reactionRoleId reaction @Role [--list] [--remove-messages] [--make]
    - Pensar melhor nisso aqui, como resolver a questão de limpar roles e a mensagem que da os roles, etc...