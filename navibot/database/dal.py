import logging
import aiomysql

from navibot.database.models import GuildVariable, VariableType, MemberInfo

class BaseDAL:
    def __init__(self, conn):
        self.conn = conn

    @staticmethod
    def map_current_object(self, row):
        raise NotImplementedError()

class MemberInfoDAL(BaseDAL):
    def map_current_object(self, row, memid: int):
        return MemberInfo(
            memid,
            row[0],
            row[1] if len(row) > 1 else None
        )

    async def get_member_info(self, memid: int):
        async with self.conn.cursor() as c:
            await c.execute(
                query='SELECT mem_exp, mem_profile_cover FROM member_info WHERE mem_id = %s LIMIT 1;',
                args=(memid, )
            )

            rows = await c.fetchone()
        
        return self.map_current_object(
            rows, 
            memid=memid
        ) if rows else None

    async def get_member_info_cacheable(self, memid: int):
        async with self.conn.cursor() as c:
            await c.execute(
                query='SELECT mem_exp FROM member_info WHERE mem_id = %s LIMIT 1;',
                args=(memid, )
            )

            rows = await c.fetchone()
        
        return self.map_current_object(
            rows, 
            memid=memid
        ) if rows else None

    async def update_member_info(self, member: MemberInfo):
        async with self.conn.cursor() as c:
            await c.execute(
                query='UPDATE member_info SET mem_exp = %s, mem_profile_cover = %s WHERE mem_id = %s;',
                args=(member.exp, member.profile_cover, member.userid)
            )

        return True

    async def update_member_info_exp_only(self, member: MemberInfo):
        async with self.conn.cursor() as c:
            await c.execute(
                query='UPDATE member_info SET mem_exp = %s WHERE mem_id = %s;',
                args=(member.exp, member.userid)
            )

        return True

    async def update_member_info_profile_cover_only(self, member: MemberInfo):
        async with self.conn.cursor() as c:
            await c.execute(
                query='UPDATE member_info SET mem_profile_cover = %s WHERE mem_id = %s;',
                args=(member.profile_cover, member.userid)
            )

        return True

    async def create_member_info(self, member: MemberInfo):
        async with self.conn.cursor() as c:
            await c.execute(
                query='INSERT INTO member_info (mem_id, mem_exp, mem_profile_cover) VALUES (%s, %s, %s);',
                args=(member.userid, member.exp, member.profile_cover)
            )

        return True

class GuildVariableDAL(BaseDAL):
    def map_current_object(self, row, guildid: int=None, key: str=None):
        # Isso e meio bizarro, mas previne qualquer input que possa estragar o mapeamento
        assert (guildid and key) or (not guildid and not key)

        # @FIXME:
        # Isso nao trata os casos aonde nós só temos um dos valores disponíveis
        offset = 0 if guildid else 2
        
        return GuildVariable(
            guildid or row[0],
            key or row[1],
            row[offset + 0],
            VariableType(row[offset + 1])
        )

    async def get_variable(self, guildid: int, key: str):
        async with self.conn.cursor() as c:
            await c.execute(
                query='SELECT gst_value, gst_value_type FROM guild_settings WHERE gui_id = %s AND gst_key = %s LIMIT 1;',
                args=(guildid, key)
            )

            rows = await c.fetchone()
        
        return self.map_current_object(
            rows, 
            guildid=guildid, 
            key=key
        ) if rows else None

    async def get_all_variables(self, guildid: int):
        async with self.conn.cursor() as c:
            await c.execute(
                query='SELECT gui_id, gst_key, gst_value, gst_value_type FROM guild_settings WHERE gui_id = %s;',
                args=(guildid, )

            )

            rows = c.fetchall()
        
        return [
            self.map_current_object(
                row
            ) 
            for row in rows
        ] if rows else rows

    async def create_variable(self, variable: GuildVariable):
        async with self.conn.cursor() as c:
            await c.execute(
                query='INSERT INTO guild_settings VALUES (%s, %s, %s, %s);',
                args=(variable.guildid, variable.key, variable.value, variable.valuetype.value)
            )

        return True

    async def update_variable(self, variable: GuildVariable):
        async with self.conn.cursor() as c:
            await c.execute(
                query='UPDATE guild_settings SET gst_value = %s, gst_value_type = %s WHERE gui_id = %s AND gst_key = %s;',
                args=(variable.value, variable.valuetype.value, variable.guildid, variable.key)
            )

        return True

    async def remove_variable(self, variable: GuildVariable):
        async with self.conn.cursor() as c:
            await c.execute(
                'DELETE FROM guild_settings WHERE gui_id = %s AND gst_key = %s;',
                args=(variable.guildid, variable.key)
            )

        return True