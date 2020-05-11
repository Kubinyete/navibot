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
- [ ] regexp
- [ ] scared (interpretado)
- [ ] hug @Usuario
    - [ ] Verificar se tem como fazer uma verificação de menções antes de executar o comando interpretado (pode falhar pois não verificamos argumentos antes)
- [ ] pat @Usuario
    - [ ] Verificar se tem como fazer uma verificação de menções antes de executar o comando interpretado (pode falhar pois não verificamos argumentos antes)
- [ ] encode [md5|base64|...]
- [ ] triggered [@Usuario] [URL] [discord_attachment]
- [ ] think [@Usuario] [URL] [discord_attachment]
- [ ] text2image [texto...]
- [ ] asciify [@Usuario] [URL] [discord_attachment]
- [ ] marry @Usuario
- [ ] divorce @Usuario
- [ ] help [cmd] --about --syntax
- [ ] showlevelupmessage [-d|--disable] [-e|--enable] @Usuario
- [ ] profile @Usuario
- [ ] credits
- [ ] shop
- [ ] buy item_id
- [ ] giveitem item_id @Usuario
- [ ] givecredits amount @Usuario
