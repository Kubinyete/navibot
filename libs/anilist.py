import aiohttp

class ErrorCollection(Exception):
    def __init__(self, errors):
        self.errors = errors

# @TODO: Fazer com que APIs retornem seus próprios objetos
class AniListApi:
    def __init__(self, aiohttpSession: aiohttp.ClientSession):
        self.session = aiohttpSession
        self.domain = r'https://graphql.anilist.co'

    async def send_request(self, query, variables={}):
        json = None

        async with self.session.post("https://graphql.anilist.co", json={
            "query": query,
            "variables": variables
        }) as resp:
            json = await resp.json()

        if 'errors' in json:
            raise ErrorCollection(
                json['errors']
            )
        else:
            return json['data']

    async def search_characters(self, search, page=1, limit=20):
        data = await self.send_request("""
query ($search:String, $page:Int, $perpage:Int) {
    Page (page: $page, perPage: $perpage) {
        characters (search: $search, sort: SEARCH_MATCH) {
            id,
            name {
                first
                last
                full
                native
            },
            image {
                large
                medium
            },
            description,
            favourites
        }
    }
}
""", variables={
    "search": search, 
    "page": page, 
    "perpage": limit
})

        return data['Page']['characters']