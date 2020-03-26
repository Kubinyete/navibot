import navibot
import logging
import math

from navibot.client import BotCommand, Slider
from navibot.errors import CommandError
from navibot.util import bytes_string

from libs.yandere import YandereApi

class CYandere(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "yandere",
            aliases = ['ynd'],
            description = "Exibe um Slider de uma ou mais imagens retornadas pela API do site yande.re de acordo com as tags informadas por argumento.",
            usage = "{name} [--post] [tag1] [tagN]... [--page=1] | --tag [tagname1...]"
        )

        self.api = YandereApi()
        
        # @TODO: Solução temporária até adicionarmos o contexto de variáveis de uma Guild
        self.allowed_ratings = ('s')
        self.tags_per_embed = 20
        self.posts_per_page = 20

    async def run(self, message, args, flags):
        if not args:
            return self.get_usage_embed(message)

        inputstr = ' '.join(args)

        try:
            page = flags.get('page', 1)
            
            if type(page) is str:
                page = int(page)
        except ValueError:
            raise CommandError("O argumento `--page` não é um número válido.")

        items = []

        if 'tag' in flags:
            tag_json = await self.api.fetch_tags(name=inputstr, order='name', limit=0)
            logging.debug(f"Received tag_json: {tag_json}")

            i = 0
            description = ""
            for tag in tag_json:
                if i and i % self.tags_per_embed == 0:
                    embed = self.create_response_embed(message, description=description)
                    embed.title = f"Lista de tag(s)"
                    items.append(embed)
                    description = ""

                description += f"`{tag['name']}` ({self.api.tagtype_string(tag['type'])}) ({tag['count']})\n"
                i += 1

            if i % self.tags_per_embed != 0:
                embed = self.create_response_embed(message, description=description)
                embed.title = f"Lista de tag(s)"
                items.append(embed)
                description = ""
        else:
            post_json = await self.api.fetch_posts(tags=inputstr, page=page, limit=self.posts_per_page)
            logging.debug(f"Received post_json: {post_json}")

            for post in post_json:
                if post['rating'] in self.allowed_ratings:
                    embed = self.create_response_embed(message)
                    
                    description = f"`{post['tags']}`\n"
                    description += f":information_source: Ver [amostra]({post['sample_url']}) ({post['sample_width']}x{post['sample_height']}) ({bytes_string(post['sample_file_size'])})\n"
                    description += f":information_source: Ver [original]({post['file_url']}) ({post['width']}x{post['height']}) ({bytes_string(post['file_size'])})\n"

                    if self.allowed_ratings:
                        description += f":warning: Algumas imagens podem não estar disponíveis devido à restrições de conteúdo (`help nsfw`)."

                    embed.title = f"{post['id']}"
                    embed.url = f"{self.api.domain}/post/show/{post['id']}"
                    embed.description = description
                    embed.set_image(url=post['preview_url'])

                    items.append(embed)

        return Slider(
            self.bot.client, 
            message,
            items
        ) if items else f":warning: Nenhum resultado encontrado para `{inputstr}`"
