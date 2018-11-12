from aiohttp import web, ClientSession
import os

routes = web.RouteTableDef()


async def twitch_aggregator_messages(request):
    stream = request.match_info['stream']

    baseurl = os.environ['IRCBOT_ENDPOINT']

    async with ClientSession() as session:
        async with session.get(f'{baseurl}/messages/{stream}') as resp:
            return web.Response(text=await resp.text(), content_type='application/json')


async def twitch_aggregator_streams(request):
    baseurl = os.environ['IRCBOT_ENDPOINT']

    async with ClientSession() as session:
        async with session.get(f'{baseurl}/streams') as resp:
            return web.Response(text=await resp.text(), content_type='application/json')


def add_route(filename):
    async def func(request):
        with open(filename) as f:
            return web.Response(text=f.read(), content_type='text/html')
    return func


def apply_routes(app):
    app.router.add_get('/', add_route('html/index.html'))
    app.router.add_get('/joevotes', add_route('html/joevotes.html'))
    app.router.add_get('/streamschedule', add_route('html/streamschedule.html'))
    app.router.add_get('/dangobango', add_route('html/dangobango.html'))
    app.router.add_get('/dangobango-popup', add_route('html/dangobango-popup.html'))
    app.router.add_get('/twitch-aggregator', add_route('html/twitch-aggregator.html'))
    app.router.add_get('/twitch-aggregator/messages/{stream}', twitch_aggregator_messages)
    app.router.add_get('/twitch-aggregator/streams/', twitch_aggregator_streams)
    app.router.add_static('/static', 'static')
