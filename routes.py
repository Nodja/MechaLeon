from aiohttp import web


async def index(request):
    with open('html/index.html') as f:
        return web.Response(text=f.read(), content_type='text/html')


async def joevotes(request):
    with open('html/joevotes.html') as f:
        return web.Response(text=f.read(), content_type='text/html')


async def streamschedule(request):
    with open('html/streamschedule.html') as f:
        return web.Response(text=f.read(), content_type='text/html')


def apply_routes(app):
    app.router.add_get('/', index)
    app.router.add_get('/joevotes', joevotes)
    app.router.add_get('/streamschedule', streamschedule)
    app.router.add_static('/static', 'static')
