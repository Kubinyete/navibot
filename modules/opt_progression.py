import discord
import asyncio
import logging
import aiohttp
import io
import math
import time
import PIL.Image
import PIL.ImageFont
import PIL.ImageDraw

from navibot.client import Bot, BotCommand, PermissionLevel, EmojiType, ClientEvent, BotContext, Plugin, IntervalContext
from navibot.errors import CommandError
from navibot.util import bytes_string, normalize_image_size
from navibot.database.dal import MemberInfoDAL
from navibot.database.models import MemberInfo

class PProgressionRewarder(Plugin):
    def __init__(self, bot):
        super().__init__(bot)
        self.manager = ProgressionManager(bot, max_level_allowed=100)

    async def on_bot_start(self):
        sync_interval = self.bot.config.get('modules.progression.sync_interval', 300)
        logging.info(f'PProgressionRewarder sync_interval for ProgressionManager is set to {sync_interval}')

    async def on_plugin_load(self):
        self.bind_event(
            ClientEvent.MESSAGE,
            self.callable_progression_receive_message
        )

        self.manager.start_processing()

    async def on_plugin_destroy(self):
        if self.manager.is_processing():
            self.manager.stop_processing()

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

        expected_message_length = self.bot.config.get('progression.expected_message_length', 50)
        expected_reward_value = self.bot.config.get('progression.expected_reward_value', 50)

        show_levelup = await self.bot.guildsettings.get_guild_variable(message.guild.id, 'pro_show_levelup')

        receive_factor = len(message.content) / expected_message_length
        if receive_factor > 1:
            receive_factor = 1

        received_exp = math.ceil(expected_reward_value * receive_factor)

        member_info, levelup = await self.manager.give_exp_reward(message.author.id, received_exp)

        if levelup and show_levelup:
            await self.handle_levelup_message(message, member_info.get_current_level())

class ProgressionManager:
    def __init__(self, bot: Bot, max_level_allowed=100):
        self.bot = bot
        self.membermap = {}
        self.pending_processing = set()
        self.max_level_allowed = max_level_allowed

        self.sync_interval = IntervalContext(
            bot.config.get('modules.progression.sync_interval', 300),
            self.callable_proccess_pending,
            ignore_exception=True
        )

    def start_processing(self):
        logging.info(f'start_processing is creating a task for sync_interval...')
        self.sync_interval.create_task()

    def stop_processing(self):
        logging.info(f'stop_processing is destroying a task for sync_interval...')
        self.sync_interval.cancel_task()

    def is_processing(self):
        logging.info(f'is_processing sync_interval is running = {self.sync_interval.is_running()}...')
        return self.sync_interval.is_running()

    async def callable_proccess_pending(self, interval: IntervalContext, kwargs: dict):
        stamp = time.perf_counter()
        logging.info(f'Starting processing of pending_processing MemberInfo queue at timestamp {stamp}...')

        # Se não fizermos uma copia, corremos o risco de nunca terminarmos de iterar sobre a lista de pendentes
        pending_copy = self.pending_processing.copy()
        self.pending_processing.clear()

        async with (await self.bot.get_connection_pool()).acquire() as conn:
            d = MemberInfoDAL(conn)

            for mem in pending_copy:
                member_exists = await d.get_member_info(mem.userid)

                if not member_exists:
                    if not await d.create_member_info(mem):
                        logging.info(f'callable_proccess_pending Failed to create_member_info for member {mem.userid} in queue.')
                else:
                    if not await d.update_member_info_exp_only(mem):
                        logging.info(f'callable_proccess_pending Failed to update_member_info_exp_only for member {mem.userid} in queue.')

        
        logging.info(f'Finished processing of pending_processing MemberInfo queue, took {time.perf_counter() - stamp} second(s).')

    async def get_cacheable_member_info(self, memid: int):
        member_info = self.membermap.get(memid, None)

        if not member_info:
            async with (await self.bot.get_connection_pool()).acquire() as conn:
                d = MemberInfoDAL(conn)
                member_info = await d.get_member_info(memid)
                member_info = member_info if member_info else MemberInfo(memid, 0, None)
                self.membermap[memid] = member_info
            
        return member_info

    async def give_exp_reward(self, memid: int, amount: int):
        member_info = await self.get_cacheable_member_info(memid)
        max_allowed_exp = MemberInfo.get_exp_required_for_level(self.max_level_allowed)

        # Nao atualiza se ja bateu o teto de EXP
        if member_info.exp < max_allowed_exp:
            prev_level = member_info.get_current_level()
            
            member_info.exp += amount
            if member_info.exp >= max_allowed_exp:
                member_info.exp = max_allowed_exp

            curr_level = member_info.get_current_level()

            if not member_info in self.pending_processing:
                self.pending_processing.add(member_info)

            return member_info, curr_level > prev_level
        else:
            return member_info, False

class CProfile(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "profile",
            aliases = ['pf'],
            description = "Exibe o perfil Navibot do próprio autor ou o do membro mencionado.",
            usage = '[@Usuario]'
        )

        self.profile_template_fl = PIL.Image.open(f'{self.bot.curr_path}/repo/profile/profile-template-fl.png')
        self.profile_template_xpbar_full = PIL.Image.open(f'{self.bot.curr_path}/repo/profile/profile-template-xpbar-full.png')

        # @NOTE:
        # Isso é um arquivo que pode ser compartilhado entre outros comandos caso necessário
        # se for preciso, fazer um sistema a parte de carregamento de fontes
        self.font_raleway_bold = PIL.ImageFont.truetype(f'{self.bot.curr_path}/repo/fonts/Raleway-Bold.ttf', size=30)

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

        pm = self.bot.plugins.get_plugin_by_type(PProgressionRewarder).manager
        member_info = await pm.get_cacheable_member_info(target.id)

        if not member_info:
            raise CommandError(f'Não foi possível encontrar as informações deste usuário, o usuário não possui um perfil ou ainda está em processamento, por favor tente novamente mais tarde.')

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
        