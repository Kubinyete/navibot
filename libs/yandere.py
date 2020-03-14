import aiohttp

class YandereApi:
    def __init__(self):
        self.session = aiohttp.ClientSession()
        self.domain = r'http://yande.re'

    async def fetch_tags(self, id=None, after_id=None, name=None, order='name', page=0, limit=20):
        assert order in ('name', 'count', 'date')
        assert limit >= 0

        async with self.session.get(f'{self.domain}/tag.json', params={
            'id': id,
            'after_id': after_id,
            'name': name,
            'order': order,
            'page': page,
            'limit': limit
        }) as response:
            return await response.json()

    async def fetch_posts(self, tags=None, page=0, limit=20):
        assert limit >= 0
        assert type(tags) is str or type(tags) is list

        async with self.session.get(f'{self.domain}/post.json', params={
            'tags': ' '.join(tags) if type(tags) is list else tags,
            'page': page,
            'limit': limit
        }) as response:
            return await response.json()