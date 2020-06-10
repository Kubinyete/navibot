import discord
import asyncio
import logging
import re
import youtube_dl
from navibot.errors import CommandError
from navibot.client import BotCommand, EmojiType, PermissionLevel

class CStop(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'stop',
            aliases = ['stp'],
            description = 'Para de tocar qualquer música que foi solicitada anteriormente, logo após, sai do canal de voz.',
            permissionlevel = PermissionLevel.BOT_OWNER
        )

    async def run(self, ctx, args, flags):
        if ctx.channel.guild.voice_client is None:
            raise CommandError('Atualmente eu não estou tocando nenhum áudio nesta Guild.')
        else:
            vclient = ctx.channel.guild.voice_client
            
            if vclient.is_playing() or vclient.is_paused():
                vclient.stop()
            
            await vclient.disconnect()

            return EmojiType.CHECK_MARK

class CPlay(BotCommand):
    def __init__(self, bot):
        super().__init__(
            bot,
            name = 'play',
            aliases = ['ply'],
            description = 'Entra no mesmo canal de voz que o autor da mensagem, tocando o URL do YouTube solicitado (Ex: ;play https://www.youtube.com/watch?v=dQw4w9WgXcQ):',
            usage = 'URL',
            permissionlevel = PermissionLevel.BOT_OWNER
        )

        # Parametros iniciais de:
        # https://github.com/Rapptz/discord.py/blob/master/examples/basic_voice.py
        self.youtubedl = youtube_dl.YoutubeDL(
            params={
                'format': 'bestaudio/best',
                'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
                'restrictfilenames': True,
                'noplaylist': True,
                'nocheckcertificate': True,
                'ignoreerrors': False,
                'logtostderr': False,
                'quiet': True,
                'no_warnings': True,
                'default_search': 'auto',
                'source_address': '0.0.0.0'
            }
        )

    async def run(self, ctx, args, flags):
        if ctx.author.voice is None or ctx.author.voice.channel is None:
            raise CommandError('Você não está conectado em nenhum canal de voz.')
        else:
            if ctx.channel.guild.voice_client is None:
                url = ''.join(args)

                # Por enquanto, para simplificarmos a primeira implementação, vamos restringir apenas ao domínio do youtube
                # https://stackoverflow.com/questions/2742813/how-to-validate-youtube-video-ids
                if not re.findall(r'^(https?://)?(www\.youtube\.com|youtu\.be)/(watch\?v=)?[a-zA-Z0-9_-]+', url):
                    raise CommandError(f'O URL `{url}` informado não é um video do YouTube válido.')
                else:
                    loop = asyncio.get_running_loop()
                    youtube_data = None

                    try:
                        youtube_data = await loop.run_in_executor(None, lambda: self.youtubedl.extract_info(url, download=False))
                    except Exception:
                        raise CommandError('Falha ao obter informações a partir da URL informada.')
                    
                    youtube_title = youtube_data['title']
                    youtube_duration = youtube_data['duration']
                    youtube_formats = youtube_data['requested_formats']

                    if not youtube_formats:
                        raise CommandError('Nenhum formato adequado foi retornado do YouTube.')

                    youtube_data_stream_url = youtube_formats[0]['url']

                    vclient = await ctx.author.voice.channel.connect()

                    def callable_after_playing(e):
                        nonlocal vclient
                        nonlocal loop
                        assert loop
                        assert vclient

                        if e:
                            logging.exception(f'callable_cleanup_after_playing threw an error: {type(e).__name__}: {e}')
                        
                        asyncio.run_coroutine_threadsafe(
                            vclient.disconnect(),
                            loop
                        )

                    vclient.play(
                        discord.PCMVolumeTransformer(
                            discord.FFmpegPCMAudio(youtube_data_stream_url), 
                            volume=.5
                        ),
                        after=callable_after_playing
                    )
            else:
                raise CommandError('Eu já estou tocando um áudio em um canal de voz, por favor tente novamente mais tarde.')

