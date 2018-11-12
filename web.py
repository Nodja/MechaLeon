import os
import sys

from aiohttp import web

from shared import app, sio, discord_client
from routes import apply_routes


sio.attach(app)


async def start_background_tasks(app):
    app.loop.create_task(discord_client.start(os.environ['DISCORD_TOKEN'], bot=False))
    app.loop.create_task(discord_client.send_votes_task())
    app.loop.create_task(discord_client.save_votes_task())


@sio.on('connect', namespace='/joevotes')
async def connect(sid, environ):
    await sio.emit('vote change', discord_client.generate_vote_data(), namespace='/joevotes', room=sid)

apply_routes(app)

app.on_startup.append(start_background_tasks)


if __name__ == '__main__':
    web.run_app(app, port=sys.argv[1])
