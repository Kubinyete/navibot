import aiohttp
import logging
from enum import Enum, auto

class Gamemode(Enum):
    OSU = 0
    TAIKO = 1
    CTB = 2
    MANIA = 3

    @staticmethod
    def public_gamemode_string(mode):
        return ('osu', 'taiko', 'fruits', 'mania')[mode.value]

    @staticmethod
    def from_gamemode_string(name):
        return getattr(Gamemode, name)

# @TODO: Fazer com que APIs retornem seus próprios objetos
class OsuApi:
    def __init__(self, key, aiohttpSession: aiohttp.ClientSession):
        self.session = aiohttpSession
        self.domain = r'https://osu.ppy.sh'
        self.key = key

    async def fetch_user(self, username, mode=Gamemode.OSU):
        async with self.session.get(f'{self.domain}/api/get_user', params={
            'k': self.key,
            'u': username,
            'm': mode.value,
            'type': 'string'
        }) as response:
            return await response.json()

    async def public_fetch_user_best(self, userid, mode=Gamemode.OSU, limit=10):
        assert limit >= 0

        async with self.session.get(f'{self.domain}/users/{userid}/scores/best', params={
            'mode': Gamemode.public_gamemode_string(mode),
            'limit': limit
        }) as response:
            return await response.json()