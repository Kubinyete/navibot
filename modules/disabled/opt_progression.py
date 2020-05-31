import discord
import asyncio
import logging
import aiohttp
import io
import math
import PIL.Image
import PIL.ImageFont
import PIL.ImageDraw

from navibot.client import Bot, BotCommand, PermissionLevel, EmojiType, ModuleHook, ClientEvent, BotContext
from navibot.errors import CommandError
from navibot.util import bytes_string, normalize_image_size
from navibot.database.dal import MemberInfoDAL

class ProgressionManager:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def get_connection_pool(self):
        return await self.bot.get_connection_pool()

    async def get_member_info(self, member: discord.Member):
        async with (await self.get_connection_pool()).acquire() as conn:
            d = MemberInfoDAL(conn)

            return await d.get_member_info(
                member.guild.id,
                member.id
            )

    async def init_member_info(self, member: discord.Member, amount: int):
        async with (await self.get_connection_pool()).acquire() as conn:
            d = MemberInfoDAL(conn)

            return await d.init_member_info(
                member.guild.id,
                member.id,
                amount
            )

    async def add_exp_to_member(self, member: discord.Member, amount: int):
        async with (await self.get_connection_pool()).acquire() as conn:
            d = MemberInfoDAL(conn)

            return await d.add_exp_to_member(
                member.guild.id,
                member.id,
                amount
            )

class HProgressionManager(ModuleHook):
    def __init__(self, bot):
        super().__init__(bot)

        self.manager = ProgressionManager(bot)

    def run(self):
        self.bind_event(
            ClientEvent.MESSAGE,
            self.callable_progression_receive_message
        )

    async def handle_levelup_message(self, message: discord.Message, currlevel: int):
        ctx = BotContext(
            self.bot,
            channel=message.channel,
            author=message.author,
            message=message
        )

        embed = ctx.create_response_embed()
        embed.colour = discord.Colour.from_rgb(0, 200, 0)
        embed.title = f'{message.author.name} subiu de nível!'
        embed.description = f'Você acabou de alcançar o nível **{currlevel}**.'

        return await ctx.reply(embed)

    async def callable_progression_receive_message(self, kwargs):
        message = kwargs.get('message')

        if not isinstance(message.channel, discord.TextChannel) or message.author == self.bot.client.user or message.author.bot:
            return

        expected_message_length, message_reward_value, show_levelup = await asyncio.gather(
            self.bot.guildsettings.get_guild_variable(message.guild.id, 'pro_expected_message_length'),
            self.bot.guildsettings.get_guild_variable(message.guild.id, 'pro_message_reward_value'),
            self.bot.guildsettings.get_guild_variable(message.guild.id, 'pro_show_levelup')
        )

        receive_factor = len(message.content) / expected_message_length.get_value()
        if receive_factor > 1:
            receive_factor = 1

        received_exp = math.ceil(message_reward_value.get_value() * receive_factor)

        async with asyncio.Lock() as lock:
            member_info = await self.manager.get_member_info(message.author)

            if not member_info:
                await self.manager.init_member_info(message.author, received_exp)
            else:
                if await self.manager.add_exp_to_member(message.author, received_exp):
                    if show_levelup.get_value():
                        prevlevel = member_info.get_current_level()
                        member_info.exp += received_exp
                        currlevel = member_info.get_current_level()

                        if currlevel > prevlevel:
                            await self.handle_levelup_message(message, currlevel)
                else:
                    logging.info('HPROGRESSIONMANAGER: ProgressionManager failed to execute add_exp_to_member')

class CProfile(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "profile",
            aliases = ['pf'],
            description = "Exibe o perfil Navibot do próprio autor ou o do membro mencionado.",
            usage = '[@Usuario]',
            permissionlevel = PermissionLevel.BOT_OWNER
        )

        local_repo = self.bot.config.get('global.local_repo', None)

        self.profile_template_fl = PIL.Image.open(
            f'{self.bot.curr_path}/repo/profile/profile-template-fl.png'
        )

        self.profile_template_xpbar_full = PIL.Image.open(
            f'{self.bot.curr_path}/repo/profile/profile-template-xpbar-full.png'
        )

        # @NOTE:
        # Isso é um arquivo que pode ser compartilhado entre outros comandos caso necessário
        # se for preciso, fazer um sistema a parte de carregamento de fontes
        self.font_raleway_bold = PIL.ImageFont.truetype(
            f'{local_repo}/fonts/Raleway-Bold.ttf',
            size=30
        )

        # Deixa os bytes em memória, para que não seja preciso ficar pegando do disco toda vez.
        self.profile_template_fl.load()
        self.profile_template_xpbar_full.load()

        self.max_image_byte_size = 512 * 1024 ^ 2
        self.max_image_size = 116
        self.prefer_discord_avatar_image_size = 128
        self.supported_file_extensions = ('png', 'jpg', 'jpeg', 'gif', 'webp')

    async def run(self, ctx, args, flags):
        mentions = flags.get('mentions', None)

        target = None

        if not mentions:
            target = ctx.author
        else:
            target = mentions[0]

        pm =  ProgressionManager(self.bot)
        member_info = await pm.get_member_info(target)

        if not member_info:
            raise CommandError(f'O seu perfil ainda não foi processado, por favor tente novamente mais tarde.')

        target_name = target.name
        xp_curr_level = member_info.get_current_level()

        xp_level_floor = member_info.get_exp_required_for_level(xp_curr_level)
        xp_level_ceil = member_info.get_exp_required_for_level(xp_curr_level + 1)
        
        xp_whole_level = xp_level_ceil - xp_level_floor
        xp_factor = (member_info.exp - xp_level_floor) / xp_whole_level

        bytes = None
        url = str(target.avatar_url_as(size=self.prefer_discord_avatar_image_size))

        try:
            async with self.bot.get_http_session().get(url) as resp:
                if resp.status == 200:
                    bytes = await resp.read()
                else:
                    raise CommandError("Não foi possível obter a imagem através da URL fornecida, o destino não retornou OK.")
        except aiohttp.ClientError as e:
            logging.exception(f'CPROFILE: {type(e).__name__}: {e}')
            raise CommandError("Não foi possível obter a imagem através da URL fornecida.")
        except asyncio.TimeoutError as e:
            logging.exception(f'CPROFILE: {type(e).__name__}: {e}')
            raise CommandError("Não foi possível obter a imagem através da URL fornecida, o tempo limite da requisição foi atingido.")
        finally:
            bio_input = io.BytesIO(bytes)

        bio_output = io.BytesIO()

        def callable_apply_profile_template():
            curr_img = None

            try:
                curr_img = PIL.Image.open(bio_input)
            except Exception:
                raise CommandError('Não foi possível abrir a imagem a partir dos dados recebidos.')

            if not curr_img.format in ('PNG', 'JPG', 'JPEG', 'GIF', 'WEBP'):
                raise CommandError('O formato da imagem é inválido.')

            curr_img = curr_img.convert(mode='RGBA')
            curr_img = normalize_image_size(curr_img, self.max_image_size)

            profile_template = self.profile_template_fl.copy()
            bar_template = self.profile_template_xpbar_full.copy()
            
            bar_template = bar_template.crop(
                (
                    0,
                    0,
                    math.floor(bar_template.width * xp_factor),
                    bar_template.height - 1
                )
            )

            # Imagem de perfil
            profile_template.paste(
                curr_img,
                # 120 + 10 border
                (
                    math.floor(120 / 2 + 10 - curr_img.width / 2), 
                    math.floor(120 / 2 + 10 - curr_img.height / 2)
                )
            )

            # Template da barra de EXP
            profile_template.paste(
                bar_template,
                # Em x: 10, y: 185
                (
                    10,
                    185
                )
            )

            draw = PIL.ImageDraw.Draw(profile_template)
            
            # Nome do usuário
            draw.text(
                (
                    140,
                    100 - self.font_raleway_bold.size - 10
                ),
                target_name,
                fill=(255, 255, 255, 255),
                font=self.font_raleway_bold,
                stroke_width=1,
                stroke_fill=(50, 50, 50, 255)
            )

            level_str = str(xp_curr_level)
            # Nível atual
            draw.text(
                (
                    120 / 2 - draw.textsize(level_str, font=self.font_raleway_bold)[0] / 2 + 10,
                    140
                ),
                level_str,
                fill=(145, 81, 213),
                font=self.font_raleway_bold
            )

            progress_str = f'{member_info.exp}/{xp_level_ceil} xp'
            # EXP restante
            draw.text(
                (
                    390 - draw.textsize(progress_str, font=self.font_raleway_bold)[0],
                    140
                ),
                progress_str,
                fill=(7, 194, 119),
                font=self.font_raleway_bold
            )

            profile_template.save(bio_output, format='PNG')

        await asyncio.get_running_loop().run_in_executor(
            None,
            callable_apply_profile_template
        )

        # @NOTE:
        # discord.py: se não voltarmos o ponteiro, não lemos nada
        bio_output.seek(0, io.SEEK_SET)
        return discord.File(
            bio_output,
            filename='profile.png'
        )