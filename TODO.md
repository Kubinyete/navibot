### TODO - Navibot

# Navibot

- [x] make-config.sh (2020-04-14 11:24:48)
- [X] Adicionar operador que desativa ~~naquela "PIPELINE"~~ a resolução de subcomandos dentro de argumentos literais. (2020-04-15 21:00:50)

# Comandos

- [ ] Implementar comandos adicionais:
    - [ ] hug @Usuario
    - [ ] pat @Usuario
    - [ ] about
        * Deve explicar o usuário como funciona o processo de parse do comando, dar exemplos de chamada de comandos usando os operadores | e {}.    
    - [ ] github
    - [ ] hotreload
    - [X] setprefix prefixo [-r|--reset] (2020-04-15 21:01:03)
        - [X] Fallback, mencionar o bot para saber o prefixo atual (2020-04-15 21:01:32)
        - [X] Fallback, mencionar o bot para resetar o prefixo (2020-04-15 21:01:34)

- [ ] Usuários de uma Guild podem ter seus próprios comandos
    - [ ] GuildCommandsManager, dicionário local (per-guild) com cache habilitado, que terá os comandos interpretados
    - [ ] addguildcommand name "cmd"
    - [ ] removeguildcommand name

# Navibot (LTG)

- [ ] Suporte a mais de uma linguagem
    * Não sei se realmente vale a pena a complexidade adicional de adicionar suporte a outras linguagens, vai depender de quais proporções queremos que esse bot tome no futuro

- [ ] Reescrever os modulos de APIs para poder utilizar uma abordagem mais genérica de se conectar uma API ao Bot.
    * Gostaria que as APIs recebessem um objeto que faz pedidos GET e POST e traga dados, internamente esse objeto estará reportando erros ao log do bot.
    * As chaves de APIs são sempre recebidas por construtor.
    * Quem fica responsável por iniciar as APIs são os próprios comandos, que podem armazená-la em seu próprio objeto.
    * O tratamento de excessões deverá ser feito durante a execução do comando, decidindo ou não se irá ser mostrado ao usuário.
    - [ ] libs/osu.py
    - [ ] modules/api_osu.py
    - [ ] libs/yandere.py
    - [ ] modules/api_yandere.py
    - [ ] libs/steam.py
    - [ ] modules/api_steam.py
    - [ ] libs/anilist.py
    - [ ] modules/api_anilist.py

- [ ] Launcher separado estilo daemon para o bot.