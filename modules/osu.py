import time

from navibot.client import BotCommand, Slider
from navibot.errors import CommandError

from libs.osu import OsuApi, Gamemode

class COsu(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "osu",
            aliases = ['os'],
            description = "Exibe um Slider com informações sobre o perfil do usuário e as suas melhores performances.",
            usage = "{name} username [--mode=osu|taiko|ctb|mania]"
        )

        self.api = OsuApi(
            self.bot.config.get('modules.osu.key')
        )

        self.assets_domain = r"https://a.ppy.sh"
        self.public_repo = self.bot.config.get('global.public_repo')
        self.max_best_scores = 10

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        inputstr = ' '.join(args)
        mode = Gamemode.OSU

        try:
            mode = Gamemode.from_gamemode_string(flags.get('mode', 'osu').upper())
        except AttributeError:
            raise CommandError("O argumento `--mode` não é um modo de jogo válido.")

        user = await self.api.fetch_user(inputstr, mode=mode)

        if not user:
            return f":warning: Nenhum usuário encontrado com o nome `{inputstr}`"
        else:
            # Este endpoint retorna sempre uma lista, mesmo se conter apenas 1 objeto.
            user = user[0]
            items = []

            profile_embed = self.create_response_embed(message)
            profile_embed.title = user['username']
            profile_embed.description = f"**#{user['pp_rank']}** (:flag_{user['country'].lower()}: **#{user['pp_country_rank']}**)"
            profile_embed.url = f"{self.api.domain}/u/{user['user_id']}"
            profile_embed.set_thumbnail(url=f"{self.assets_domain}/{user['user_id']}?t={time.time()}")
            # @TODO: Mostrar join_date de forma amigável
            profile_embed.add_field(name="Data de criação", value=user['join_date'], inline=True),
            # @TODO: Mostrar total_seconds_played de forma amigável
            profile_embed.add_field(name="Tempo de jogo", value=f"{int(user['total_seconds_played']) / 86400.0 if user['total_seconds_played'] is not None else 0:.2f} day(s)", inline=True),
            profile_embed.add_field(name="Vezes jogadas", value=user['playcount'], inline=True),
            profile_embed.add_field(name="PP", value=user['pp_raw'], inline=True),
            profile_embed.add_field(name="Precisão", value=f"{float(user['accuracy']) if user['accuracy'] is not None else 0:.2f}", inline=True),
            profile_embed.add_field(name="Nível", value=f"{float(user['level']) if user['level'] is not None else 0:.2f}", inline=True)

            items.append(profile_embed)

            user_best = await self.api.public_fetch_user_best(user['user_id'], mode=mode, limit=self.max_best_scores)

            for score in user_best:
                beatmap = score['beatmap']
                beatmapset = score['beatmapset']

                embed = self.create_response_embed(message)
                embed.title = f"{beatmapset['title']} por {beatmapset['artist']} [{beatmap['version']}]"
                embed.url = beatmap['url']
                embed.set_image(url=beatmapset['covers']['card'])
                embed.set_thumbnail(url=f"{self.public_repo}/osu/rank_{score['rank']}.png")
                embed.add_field(name="Mods", value=", ".join(score['mods']) if len(score['mods']) > 0 else "Not used", inline=True)
                embed.add_field(name="Accuracy", value=f"{score['accuracy'] * 100:.2f}", inline=True)
                embed.add_field(name="Combo", value=f"{score['max_combo']}x", inline=True)
                embed.add_field(name="PP", value=f"{score['pp']:.2f}pp ({score['weight']['pp']:.2f}pp {score['weight']['percentage']:.2f}%)", inline=True)
                embed.add_field(name="Stars", value=f":star: {beatmap['difficulty_rating']}", inline=True)

                items.append(embed)

            return Slider(
                self.bot.client, 
                message,
                items
            )