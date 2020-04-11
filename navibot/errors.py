# Errors module

# Utilizado quando o bot encontra um erro esperado internamente, Ex: interpretar o comando.
class BotError(Exception):
    pass

# Utilizado quando o nível de permissão da pessoa que ativou o comando não é o adequado.
class PermissionLevelError(Exception):
    pass

# Utilizado quando o Parser encontra um erro.
class ParserError(Exception):
    pass

# Utilizado pelo comando para abortar a execução.
class CommandError(Exception):
    pass

# Utilizado por erros relacionados ao banco de dados embutido.
class DatabaseError(Exception):
    pass