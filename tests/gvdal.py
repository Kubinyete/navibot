#!/usr/bin/python3
import asyncio

from databases import Database
from navibot.client import Config
from navibot.database.dal import GuildVariableDAL, GuildVariable

async def main():
    c = Config('release/config.json')
    c.load()

    database = Database(c.get('database.connection_string'))
    await database.connect()
    
    dal = GuildVariableDAL(database)

    var = GuildVariable(
        606547405164380214,
        'teste',
        '123',
        None
    )

    print(f"All guild variables = {await dal.get_all_variables(606547405164380214)}")

    print(f"Creating variable teste, return val is = {await dal.create_variable(var)}")

    print(f"All guild variables = {await dal.get_all_variables(606547405164380214)}")

    var.set_value('1234')

    input('...')
    print(f"Updating variable teste, return val is = {await dal.update_variable(var)}")
    input('...')
    print(f"Deleting variable teste, return val is = {await dal.remove_variable(var)}")
    
    print(f"All guild variables = {await dal.get_all_variables(606547405164380214)}")
    
if __name__ == "__main__":
    asyncio.run(main())