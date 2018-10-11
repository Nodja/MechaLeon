from aiohttp import web


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
    app.router.add_static('/static', 'static')
