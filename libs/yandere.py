import aiohttp

class YandereApi:
    def __init__(self, aiohttpSession=aiohttp.ClientSession()):
        self.session = aiohttpSession
        self.domain = r'https://yande.re'

    @staticmethod
    def tagtype_string(id):
        # tag[tag_type] The tag type. General: 0, artist: 1, copyright: 3, character: 4.
        # Estranho, tag type 5 existe porém não há nada escrito sobre em
        # yande.re/help/api
        try:
            return ('general', 'artist', 'unknown', 'copyright', 'character')[id]
        except IndexError:
            return 'unknown'

    async def fetch_tags(self, id=None, after_id=None, name=None, order='name', page=1, limit=20):
        assert order in ('name', 'count', 'date')
        assert limit >= 0

        params = {
            'page': page,
            'limit': limit,
            'order': order
        }

        if id:
            params['id'] = id
        elif after_id:
            params['after_id'] = after_id
        elif name:
            params['name'] = name

        async with self.session.get(f'{self.domain}/tag.json', params=params) as response:
            return await response.json()

    async def fetch_posts(self, tags='', page=1, limit=20):
        assert limit >= 0
        assert type(tags) is str or type(tags) is list

        async with self.session.get(f'{self.domain}/post.json', params={
            'tags': ' '.join(tags) if type(tags) is list else tags,
            'page': page,
            'limit': limit
        }) as response:
            return await response.json()