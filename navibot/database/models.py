import math

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
    def __init__(self, guildid: int, key: str, value, valuetype: VariableType, fetched_at: int=0):
        self.guildid = guildid
        self.key = key
        self.valuetype = valuetype or VariableType.get_enum_for_type(type(value))
        self.fetched_at = fetched_at

        self.set_value(value)

    def set_value(self, value):
        self.value = VariableType.convert_value_totype(value, self.valuetype)

    def get_value(self):
        return self.value

class MemberInfo:
    def __init__(self, guildid: int, userid: int, exp: int, profile_cover: bytes):
        self.guildid = guildid
        self.userid = userid
        self.exp = exp
        self.profile_cover = profile_cover

    @staticmethod
    def get_level_from_exp(exp: int):
        return math.floor(math.sqrt(2) * math.sqrt(exp) / 10.0)

    @staticmethod
    def get_exp_required_for_level(level: int):
        return int(50 * math.pow(level, 2))

    def get_current_level(self):
        return self.get_level_from_exp(self.exp)

    def get_required_for_next_level(self):
        return self.get_exp_required_for_level(self.get_current_level() + 1) - self.exp

    def has_profile_cover(self):
        return self.profile_cover is not None