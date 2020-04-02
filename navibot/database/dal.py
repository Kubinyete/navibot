from databases import Database

from navibot.database.models import GuildVariable, VariableType

class BaseDAL:
    def __init__(self, conn: Database):
        self.conn = conn

    @staticmethod
    def map_current_object(self, row):
        raise NotImplementedError()

class GuildVariableDAL(BaseDAL):
    def map_current_object(self, row, guildid: int=None, key: str=None):
        return GuildVariable(
            guildid or int(row['gui_id']),
            key or str(row['gst_key']),
            str(row['gst_value']),
            VariableType(int(row['gst_value_type']))
        )

    async def get_variable(self, guildid: int, key: str):
        rows = await self.conn.fetch_one(
            query='SELECT gst_value, gst_value_type FROM guild_settings WHERE gui_id = :id AND gst_key = :key',
            values={
                'id': guildid,
                'key': key
            }
        )

        return self.map_current_object(rows, guildid=guildid, key=key) if rows else None

    async def get_all_variables(self, guildid: int):
        rows = await self.conn.fetch_all(
            query='SELECT gst_key, gst_value, gst_value_type FROM guild_settings WHERE gui_id = :id',
            values={
                'id': guildid
            }
        )

        return [self.map_current_object(row, guildid=guildid) for row in rows] if rows else []

    async def create_variable(self, variable: GuildVariable):
        return not await self.conn.execute(
            query='INSERT INTO guild_settings VALUES (:id, :key, :value, :type)',
            values={
                'id': variable.guildid,
                'key': variable.key,
                'value': variable.value,
                'type': variable.valuetype.value
            }
        )

    async def update_variable(self, variable: GuildVariable):
        return not await self.conn.execute(
            query='UPDATE guild_settings SET gst_value = :value, gst_value_type = :type WHERE gui_id = :id AND gst_key = :key',
            values={
                'id': variable.guildid,
                'key': variable.key,
                'value': variable.value,
                'type': variable.valuetype.value
            }
        )

    async def remove_variable(self, variable: GuildVariable):
        return not await self.conn.execute(
            query='DELETE FROM guild_settings WHERE gui_id = :id AND gst_key = :key',
            values={
                'id': variable.guildid,
                'key': variable.key
            }
        )
    