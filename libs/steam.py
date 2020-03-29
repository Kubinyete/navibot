import aiohttp
import logging
from enum import Enum, auto

# @TODO: Fazer com que APIs retornem seus próprios objetos
class SteamApi:
    def __init__(self, key, aiohttpSession=aiohttp.ClientSession()):
        self.domain = "http://api.steampowered.com"
        self.session = aiohttpSession
        self.key = key

    @staticmethod
    def personastate_string(personastate):
        try:
            return ('Offline', 'Online', 'Busy', 'Away', 'Snooze', 'Looking to trade', 'Looking to play')[personastate]
        except IndexError:
            return 'Unknown'

    async def get_player_summaries(self, steamids):
        async with self.session.get(f"{self.domain}/ISteamUser/GetPlayerSummaries/v2/", params={
            "key": self.key,
            "steamids": ','.join([str(i) for i in steamids]),
            "format": "json"
        }) as resp:
            return await resp.json()
    
    async def get_steam_level(self, steamid):
        async with self.session.get(f"{self.domain}/IPlayerService/GetSteamLevel/v1/", params={
            "key": self.key,
            "steamid": steamid,
            "format": "json"
        }) as resp:
            return await resp.json()
    
    async def resolve_vanity_url(self, vanityurl):
        async with self.session.get(f"{self.domain}/ISteamUser/ResolveVanityURL/v1/", params={
            "key": self.key,
            "vanityurl": vanityurl,
            "format": "json",
            "url_type": 1
        }) as resp:
            return await resp.json()
    