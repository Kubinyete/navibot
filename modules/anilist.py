import io

from navibot.client import BotCommand, Slider
from navibot.errors import CommandError

from libs.anilist import AniListApi

class CAnilist(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "anilist",
            aliases = ['anl'],
            description = "Exibe um Slider com o resultados de uma pesquisa por personagens utilizando `--character`.",
            usage = "[-c|--character] [busca...] [page=1]"
        )

        self.api = AniListApi()

    async def run(self, message, args, flags):
        if 'character' in flags or 'c' in flags:
            try:
                page = flags.get('page', 1)

                if type(page) is str:
                    page = int(page)

                if page <= 0:
                    page = 1
            except ValueError:
                raise CommandError("É preciso informar um número ")

            characters = await self.api.search_characters(' '.join(args), page=page, limit=20)

            if characters:
                items = []

                for c in characters:
                    embed = self.create_response_embed(message)
                    embed.title = f"{c['name']['full']}" if not c['name'].get('native', False) else f"{c['name']['full']} ({c['name']['native']})"
                    embed.description = self.format_anilist_description(c['description'])
                    embed.set_thumbnail(url=c['image']['large'])
                    embed.add_field(name='Favourites', value=f":heart: {c['favourites']}")

                    items.append(embed)

                return Slider(
                    self.bot,
                    message,
                    items
                )
            else:
                return ':information_source: Não foi encontrando nenhum personagem.'
        else:
            return self.get_usage_embed(message)
    
    @staticmethod
    def format_anilist_description(description):
        if description and len(description) > 0:
            spoiler = False
            ignore_next = False
            fdes = io.StringIO()

            for i in range(len(description)):
                c = description[i]
                cnext = description[i + 1] if i + 1 < len(description) else ''

                if fdes.tell() >= 2043:
                    if spoiler:
                        fdes.write("...||")
                    else:
                        fdes.write("...")
                    break
                elif ignore_next:
                    ignore_next = False
                elif c == "~" and cnext == "!" and not spoiler:
                    spoiler = True
                    ignore_next = True
                    fdes.write("||")
                elif c == "!" and cnext == "~" and spoiler:
                    spoiler = False
                    ignore_next = True
                    fdes.write("||")
                else:
                    fdes.write(c)

            return fdes.getvalue()
        else:
            return "Nenhuma descrição está disponível."