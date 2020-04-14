import asyncio

from navibot.client import BotCommand, Slider
from navibot.errors import CommandError

from libs.steam import SteamApi

class CSteam(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "steam",
            aliases = ['stm'],
            description = "Exibe um perfil Steam da comunidade.",
            usage = "steamID|customURL"
        )

        self.api = SteamApi(
            self.bot.config.get('modules.steam.key')
        )

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        ident = args[0]

        try:
            ident = int(ident)
        except ValueError:
            # Assume que o valor recebido é uma URL
            pass

        if isinstance(ident, str):
            response = await self.api.resolve_vanity_url(ident)
            if response:
                response = response['response']
            else:
                raise CommandError(f"Não foi receber uma resposta dos servidores Steam.")

            if response['success'] != 1:
                raise CommandError(f"Não foi possível resolver o URL customizado para `{ident}`, por favor verifique o URL informado.")

            ident = int(response['steamid'])

        response = await self.api.get_player_summaries([ident])
        
        if response:
            response = response['response']
        else:
            raise CommandError(f"Não foi receber uma resposta dos servidores Steam.")

        if not response['players']:
            return f':information_source: Nenhum jogador com o ID/URL `{args[0]}` foi encontrado.' 
        else:
            player = response['players'][0]
            
            level = (await asyncio.gather(
                self.api.get_steam_level(ident)
            ))[0]

            level = level['response']['player_level']

            items = []

            embed = self.create_response_embed(message)
            embed.title = player['personaname']
            embed.url = player['profileurl']
            embed.set_thumbnail(url=player['avatarfull'])
            
            embed.add_field(name='SteamID', value=player['steamid'], inline=True)
            embed.add_field(name='Visibilidade', value='Private or Friends-only' if player['communityvisibilitystate'] != 3 else 'Public', inline=True)
            embed.add_field(name='Nível', value=level, inline=True)
            embed.add_field(name='Status', value=self.api.personastate_string(player['personastate']), inline=True)

            country = player.get('loccountrycode', None)
            if country:
                embed.add_field(name='País', value=f':flag_{country.lower()}:', inline=True)

            realname = player.get('realname', None)
            if realname:
                embed.add_field(name='Nome real', value=realname, inline=True)

            items.append(embed)

            return Slider(
                self.bot,
                message,
                items
            )