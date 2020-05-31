import logging
# import aiomysql
# import asyncio

# @NOTE:
# Retirada à referência ao modulo databases
# pois o mesmo não se encaixa no nosso caso de uso
# precisamos de suporte à pools de conexões, para poder
# trabalhar de modo assíncrono
# from databases import Database

from navibot.database.models import GuildVariable, VariableType, MemberInfo

class BaseDAL:
    def __init__(self, conn):
        self.conn = conn

    @staticmethod
    def map_current_object(self, row):
        raise NotImplementedError()

class MemberInfoDAL(BaseDAL):
    def map_current_object(self, row, guildid: int, memid: int):
        return MemberInfo(
            guildid,
            memid,
            row[0],
            row[1]
        )

    async def get_member_info(self, guildid: int, memid: int):
        async with self.conn.cursor() as c:
            await c.execute(
                query='SELECT mem_exp, mem_profile_cover FROM member_info WHERE gui_id = %s AND mem_id = %s LIMIT 1;',
                args=(guildid, memid)
            )

            rows = await c.fetchone()

            return self.map_current_object(
                rows, 
                guildid=guildid,
                memid=memid
            ) if rows else None

    async def add_exp_to_member(self, guildid: int, memid: int, amount: int):
        async with self.conn.cursor() as c:
            await c.execute(
                query='UPDATE member_info SET mem_exp = mem_exp + %s WHERE gui_id = %s AND mem_id = %s',
                args=(amount, guildid, memid)
            )

            await self.conn.commit()
            return True

    async def init_member_info(self, guildid: int, memid: int, amount: int):
        async with self.conn.cursor() as c:
            await c.execute(
                query='INSERT INTO member_info (gui_id, mem_id, mem_exp) VALUES (%s, %s, %s)',
                args=(guildid, memid, amount)
            )

            await self.conn.commit()
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

            await self.conn.commit()
            return True


    async def update_variable(self, variable: GuildVariable):
        async with self.conn.cursor() as c:
            await c.execute(
                query='UPDATE guild_settings SET gst_value = %s, gst_value_type = %s WHERE gui_id = %s AND gst_key = %s;',
                args=(variable.guildid, variable.key, variable.value, variable.valuetype.value)
            
            )

            await self.conn.commit()
            return True

    async def remove_variable(self, variable: GuildVariable):
        async with self.conn.cursor() as c:
            await c.execute(
                'DELETE FROM guild_settings WHERE gui_id = %s AND gst_key = %s;',
                args=(variable.guildid, variable.key)
            )

            await self.conn.commit()
            return True