from aiohttp import web

import socketio


app = web.Application()
sio = socketio.AsyncServer()


from votes import VoteCounter
discord_client = VoteCounter()
