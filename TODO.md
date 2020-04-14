### TODO - Navibot

- [x] make-config.sh (2020-04-14 11:24:48)

- [ ] Implementar comandos adicionais:
    1. hug
    2. pat
    3. about
    4. prefix (por Guild)
        1. Fallback, mencionar o bot para saber o prefixo atual
        2. Tentar filtrar os prefixos que são passados para o comando prefix

- [ ] Suporte a mais de uma linguagem
    1. pt-br
    2. en

- [ ] Adicionar operador que desativa, naquela "PIPELINE" a resolução de subcomandos dentro de argumentos literais.
    Caso de uso: ;;! addcommand teste "embed -t \"{fw Nao preciso dar escape nos operadores '{' e '}'!}\""

- [ ] Manual de utilização da "linguagem" de redirecionamento de saída dos comandos e subcomandos em argumentos literais.
    Usar um comando para demonstrar a utilizade.
    
    Possívelmente CHelp?
        ;;help syntax

- [ ] Usuários de uma Guild podem ter seus próprios comandos?
    1. Dicionário global com comandos mapeados globalmente
    2. Dicionário local (per-guild) que terá os comandos interpretados
        1. GuildCommandManager (semelhante a GuildSettingsManager)
        2. CAddCommand e CRemoveCommand disponível para GUILD_MODs

- [ ] Usuários de uma Guild podem ter suas prórpias variáveis?
    Talvez, não sei ao certo pois uma Guild poderia spammar e ter N variáveis...

- [ ] Reescrever os modulos de APIs para poder utilizar uma abordagem mais genérica de se conectar uma API ao Bot.
    1. Gostaria que as APIs recebessem um objeto que faz pedidos GET e POST e traga dados, internamente esse objeto estará reportando erros ao log do bot.
    2. As chaves de APIs são sempre recebidas por construtor.
    3. Quem fica responsável por iniciar as APIs são os próprios comandos, que podem armazená-la em seu próprio objeto.
    4. O tratamento de excessões deverá ser feito durante a execução do comando, decidindo ou não se irá ser mostrado ao usuário.

    - [ ] libs/osu.py
    - [ ] modules/api_osu.py
    - [ ] libs/yandere.py
    - [ ] modules/api_yandere.py
    - [ ] libs/steam.py
    - [ ] modules/api_steam.py
    - [ ] libs/anilist.py
    - [ ] modules/api_anilist.py

- [ ] Launcher separado estilo daemon para o bot.