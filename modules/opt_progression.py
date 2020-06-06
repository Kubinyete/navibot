import discord
import asyncio
import logging
import aiohttp
import io
import math
import time
import copy
import PIL.Image
import PIL.ImageFont
import PIL.ImageDraw
import PIL.ImageFilter

from navibot.helpers import IntervalContext
from navibot.errors import CommandError
from navibot.client import Bot, BotCommand, PermissionLevel, EmojiType, ClientEvent, BotContext, Plugin
from navibot.util import bytes_string, normalize_image_max_size, normalize_image_fit_into
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

        if levelup and show_levelup.get_value():
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
                # @TODO:
                # Isso é bizarro, mas por enquanto vamos pegar novamente o membro,
                # trocar para isso:
                # d.member_info_exists(mem.userid)
                # Após ser implementado
                member_exists = await d.get_member_info(mem.userid)

                if not member_exists:
                    if not await d.create_member_info(mem):
                        logging.info(f'callable_proccess_pending Failed to create_member_info for member {mem.userid} in queue.')
                else:
                    if member_exists.exp != mem.exp:
                        if not await d.update_member_info_exp_only(mem):
                            logging.info(f'callable_proccess_pending Failed to update_member_info_exp_only for member {mem.userid} in queue.')
        
        logging.info(f'Finished processing of pending_processing MemberInfo queue, took {time.perf_counter() - stamp} second(s).')

    @staticmethod
    def apply_uncacheable_attributes(cached_ver: MemberInfo, database_ver: MemberInfo):
        # @NOTE:
        # Esse método é necessário para juntar uma versão que esteja em cache, ou seja, contendo somente informações que são atualizadas constantemente (EXP)
        # com atributos que só são obtidos do banco de dados quando necessários, pois não podem ficar em memória por muito tempo (espaço gasto atoa).

        # Copia a instância em cache, pois essa instância está diretamente ligada ao dicionário de cache, e esse objeto não pode ser alterado diretamente
        # em casos de atributos que não podem ficar em cache
        instance = copy.copy(cached_ver)
        # Aplica...
        instance.profile_cover = database_ver.profile_cover

        return instance

    async def fetch_member_info(self, memid: int):
        async with (await self.bot.get_connection_pool()).acquire() as conn:
            d = MemberInfoDAL(conn)
            return await d.get_member_info(memid)

    async def fetch_member_info_cacheable(self, memid: int):
        async with (await self.bot.get_connection_pool()).acquire() as conn:
            d = MemberInfoDAL(conn)
            return await d.get_member_info_cacheable(memid)

    async def fetch_member_info_full(self, memid: int):
        in_cache = await self.get_cacheable_member_info(memid)

        # @NOTE:
        # Só lembrando, que get_cacheable_member_info, pode retornar uma instância em cache,
        # o que está certo neste caso, mas também pode retornar uma nova instância direta do banco
        # que acabou de ser carregada em cache, ou seja, in_cache e in_db vão estar identicos

        if in_cache:
            in_db = await self.fetch_member_info(memid)
            
            if in_db:
                return self.apply_uncacheable_attributes(in_cache, in_db)
            else:
                # Nossa versão em cache é obsoleta?
                # por hora, não faça nada
                return in_cache
        else:
            # Não achou
            return in_cache

    async def get_cacheable_member_info(self, memid: int):
        member_info = self.membermap.get(memid, None)

        if not member_info:
            member_info = await self.fetch_member_info_cacheable(memid)
            
            if not member_info:
                member_info = MemberInfo(memid, 0, None)

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

    # @NOTE: Precisamos disso aqui para que, alem de MemberInfo ser alterado em cache
    # que seja feita a alteração instanamente no banco, caso o usuário mude sua profile_cover
    async def update_member_info_profile_cover_only(self, member_info: MemberInfo):
        async with (await self.bot.get_connection_pool()).acquire() as conn:
            d = MemberInfoDAL(conn)
            return await d.update_member_info_profile_cover_only(member_info)

class CSetProfileCover(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = "setprofilecover",
            aliases = ['setpfc'],
            description = "Atualiza a imagem de fundo do perfil do usuário de acordo com a imagem informada, caso nenhum argumento ou arquivo for informado através do operador |, este comando tentará pegar a ultima imagem enviada no canal que atenda os requisitos.",
            usage = '[URL] [discord.File] [-r|--remove]',
            supported_args_type = (str, discord.File)
        )

        self.store_profile_cover_with_max_size = 512

    async def run(self, ctx, args, flags):
        pm = self.bot.plugins.get_plugin_by_type(PProgressionRewarder).manager
        member_info = await pm.get_cacheable_member_info(ctx.author.id)
        
        if not member_info:
            raise CommandError(f'Não foi possível encontrar as informações deste usuário, o usuário não possui um perfil ou ainda está em processamento, por favor tente novamente mais tarde.')

        is_removing = 'remove' in flags or 'r' in flags

        bg = None
        if not is_removing:
            bg = await self.get_image_target(ctx, args, flags, from_mention=False, from_arg=True, from_pipeline=True, from_history=True)

        if bg:
            bytedata = io.BytesIO()

            def callable_resize_and_save_image():
                nonlocal bg
                bg = normalize_image_max_size(bg.convert(mode='RGB'), self.store_profile_cover_with_max_size)
                bg.save(bytedata, format='JPEG')

            await asyncio.get_running_loop().run_in_executor(
                None,
                callable_resize_and_save_image
            )

            bytedata.seek(0, io.SEEK_SET)
            member_info.profile_cover = bytedata.getvalue()
        else:
            if is_removing:
                member_info.profile_cover = None
            else:
                return self.get_usage_embed(ctx)

        if await pm.update_member_info_profile_cover_only(member_info):
            return EmojiType.CHECK_MARK
        else:
            return EmojiType.CROSS_MARK

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
        self.profile_template_fl.load()
        self.profile_template_xpbar_full.load()

        # @NOTE:
        # Isso é um arquivo que pode ser compartilhado entre outros comandos caso necessário
        # se for preciso, fazer um sistema a parte de carregamento de fontes
        self.font_raleway_bold = PIL.ImageFont.truetype(f'{self.bot.curr_path}/repo/fonts/Raleway-Bold.ttf', size=30)

        # Deixa os bytes em memória, para que não seja preciso ficar pegando do disco toda vez.

        self.max_image_size = 116
        self.prefered_avatar_size = 128

    async def run(self, ctx, args, flags):
        prefered_image_output_format = self.get_prefered_output_image_format()

        mentions = flags.get('mentions', None)
        target = None

        if not mentions:
            target = ctx.author
        else:
            target = mentions[0]

        pm = self.bot.plugins.get_plugin_by_type(PProgressionRewarder).manager
        member_info = await pm.fetch_member_info_full(target.id)


        if not member_info:
            raise CommandError(f'Não foi possível encontrar as informações deste usuário, o usuário não possui um perfil ou ainda está em processamento, por favor tente novamente mais tarde.')

        target_name = target.name
        xp_curr_level = member_info.get_current_level()
        xp_level_floor = member_info.get_exp_required_for_level(xp_curr_level)
        xp_level_ceil = member_info.get_exp_required_for_level(xp_curr_level + 1)
        xp_whole_level = xp_level_ceil - xp_level_floor
        xp_factor = (member_info.exp - xp_level_floor) / xp_whole_level

        profile_avatar = await self.get_image_object_from_bytes(await self.get_file_from_url(str(target.avatar_url_as(size=self.prefered_avatar_size)), max_size=self.get_prefered_max_image_byte_size()))
        profile_background = None

        if member_info.profile_cover:
            profile_background = await self.get_image_object_from_bytes(io.BytesIO(member_info.profile_cover))

        output = io.BytesIO()

        def callable_apply_profile_template():
            nonlocal profile_avatar
            nonlocal profile_background

            profile_avatar = normalize_image_max_size(profile_avatar.convert(mode='RGBA'), self.max_image_size)
            profile_base = PIL.Image.new(mode='RGBA', size=(self.profile_template_fl.width, self.profile_template_fl.height), color=(255, 255, 255, 255))
            profile_background = profile_background if profile_background else profile_avatar.filter(PIL.ImageFilter.BoxBlur(6))

            if profile_background:
                # Aplicando o plano de fundo caso ele exista
                profile_base.paste(
                    normalize_image_fit_into(profile_background.convert(mode='RGBA'), profile_base.width, profile_base.height),
                    (
                        0,
                        0
                    )
                )

            # Aplicando primeira camada do design do perfil
            profile_base.paste(
                self.profile_template_fl,
                (
                    0,
                    0
                ),
                self.profile_template_fl
            )

            # Colando o avatar no perfil
            profile_base.paste(
                profile_avatar,
                # 120 + 10 border
                (
                    math.floor(120 / 2 + 10 - profile_avatar.width / 2), 
                    math.floor(120 / 2 + 10 - profile_avatar.height / 2)
                )
            )

            # Colando a barra de EXP
            profile_base.paste(
                self.profile_template_xpbar_full.crop(
                    (
                        0,
                        0,
                        math.floor(self.profile_template_xpbar_full.width * xp_factor),
                        self.profile_template_xpbar_full.height - 1
                    )
                ),
                # Em x: 10, y: 185
                (
                    10,
                    185
                )
            )

            draw = PIL.ImageDraw.Draw(profile_base)
            
            # Escrevendo nome do usuário
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

            # Escrevendo nível atual
            level_str = str(xp_curr_level)
            draw.text(
                (
                    120 / 2 - draw.textsize(level_str, font=self.font_raleway_bold)[0] / 2 + 10,
                    140
                ),
                level_str,
                fill=(145, 81, 213),
                font=self.font_raleway_bold
            )

            # Escrevendo progresso de EXP
            progress_str = f'{member_info.exp}/{xp_level_ceil} xp'
            draw.text(
                (
                    390 - draw.textsize(progress_str, font=self.font_raleway_bold)[0],
                    140
                ),
                progress_str,
                fill=(7, 194, 119),
                font=self.font_raleway_bold
            )

            # Salvando em um objeto BytesIO
            profile_base.save(output, format=prefered_image_output_format.upper())

        await asyncio.get_running_loop().run_in_executor(
            None,
            callable_apply_profile_template
        )

        output.seek(0, io.SEEK_SET)
        return discord.File(
            output,
            filename=f'profile.{prefered_image_output_format}'
        )
        