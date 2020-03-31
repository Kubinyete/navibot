from enum import Enum, auto

class VariableType(Enum):
    STRING = 0
    INT = 1
    FLOAT = 2
    BOOL = 3

    @staticmethod
    def convert_value_totype(value, valuetype):
        if valuetype is VariableType.BOOL:
            return str(value).lower() in ('1', 'yes', 'enabled', 'true')
        elif valuetype is VariableType.FLOAT:
            return float(value)
        elif valuetype is VariableType.INT:
            return int(value)
        else:
            return str(value)

    @staticmethod
    def get_enum_for_type(typec):
        return VariableType(
            (str, int, float, bool).index(typec)
        )

class GuildVariable:
    def __init__(self, guildid: int, key: str, value, valuetype: VariableType):
        self.guildid = guildid
        self.key = key
        self.valuetype = valuetype or VariableType.get_enum_for_type(type(value))

        self.set_value(value)

    def set_value(self, value):
        self.value = VariableType.convert_value_totype(value, self.valuetype)

    def get_value(self):
        return self.value