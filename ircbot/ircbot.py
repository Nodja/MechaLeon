import sys
import irc.bot
import requests
import re
import traceback
import sqlite3
import datetime
import os
import asyncio
import json

from aiohttp import web
from concurrent.futures import ThreadPoolExecutor

app = web.Application()


class TwitchBot(irc.bot.SingleServerIRCBot):
    def __init__(self, username, client_id, token, channel):
        self.client_id = client_id
        self.token = token
        self.channel = '#' + channel

        server = 'irc.chat.twitch.tv'
        port = 6667

        print(f"Connecting to {server} on port {port}")
        irc.bot.SingleServerIRCBot.__init__(
            self, [(server, port, 'oauth:' + token)], username, username)

        self.db = sqlite3.connect('ircbot.db')
        self.cursor = self.db.cursor()
        self._urlcache = [row[0] for row in self.cursor.execute('select url from links')]
        self.live = False
        self._live_rowid = None

    def on_welcome(self, c, e):
        print('Joining ' + self.channel)

        c.cap('REQ', ':twitch.tv/membership')
        c.cap('REQ', ':twitch.tv/tags')
        c.cap('REQ', ':twitch.tv/commands')
        c.join(self.channel)
        self.connection.set_keepalive(50)

    def on_pubmsg(self, c, e):
        if e.arguments[0][:1] == '!':
            cmd = e.arguments[0].split(' ')[0][1:]
            print('Received command: ' + cmd)
            try:
                self.do_command(e, cmd)
            except Exception:
                traceback.print_exc()
        else:
            msg = e.arguments[0]
            user = ''
            timestamp = datetime.datetime.utcnow().isoformat()

            for tag in e.tags:
                if tag['key'] == 'display-name':
                    user = tag['value']

            self.store_message(timestamp, user, msg)

        return

    def do_command(self, e, cmd):
        pass

        # c = self.connection
        # if cmd == "fanart":
        #     c.privmsg(self.channel, 'test weee')

    def store_message(self, timestamp, user, msg):
        urls = []
        for word in msg.split(' '):
            if word.lower().startswith('http'):
                urls.append(word)

        if urls:
            newurl = False
            for url in urls:
                if url not in self._urlcache:
                    self._urlcache.append(url)
                    self.cursor.execute('insert into links values(?)', (url, ))
                    newurl = True

            if newurl:
                print(user, msg)
                self.cursor.execute('insert into messages values(?,?,?,?)', (self.channel.strip(), timestamp, user, msg))
                self.db.commit()


async def runbot():
    auth = os.environ['IRC_AUTH'].split(' ')

    username = auth[0]
    client_id = auth[1]
    token = auth[2]
    channel = auth[3]

    def _run():
        bot = TwitchBot(username, client_id, token, channel)
        bot.start()

    while True:
        try:
            await app.loop.run_in_executor(ThreadPoolExecutor(), _run)
        except Exception:
            traceback.print_exc()
            db.close()


async def check_live():
    auth = os.environ['IRC_AUTH'].split(' ')

    username = auth[0]
    client_id = auth[1]
    token = auth[2]
    channel = auth[3].strip()

    # Get the channel id, we will need this for v5 API calls
    url = 'https://api.twitch.tv/kraken/users?login=' + channel
    headers = {'Client-ID': client_id, 'Accept': 'application/vnd.twitchtv.v5+json'}
    r = requests.get(url, headers=headers).json()

    channel_id = r['users'][0]['_id']
    live = False
    cursor = db.cursor()

    while True:
        url = 'https://api.twitch.tv/kraken/streams/' + channel_id
        headers = {'Client-ID': client_id, 'Accept': 'application/vnd.twitchtv.v5+json'}
        r = requests.get(url, headers=headers).json()

        now_live = False
        if r['stream']:
            now_live = True

        if not live and now_live:
            now = datetime.datetime.utcnow()
            now = now - datetime.timedelta(minutes=5)  # for safety
            now = now.isoformat()

            cursor.execute('insert into streams values(?,?,?,?)', (channel, r['stream']['channel']['status'], now, None))
            db.commit()
            live = True

        await asyncio.sleep(120)


async def on_startup(app):
    app.loop.create_task(runbot())
    app.loop.create_task(check_live())


async def get_messages(request):

    stream = request.match_info['stream']
    cursor = db.cursor()

    streamdates = cursor.execute("select name, start, end from streams where rowid = ?", (stream, )).fetchone()
    if streamdates:
        start = streamdates[1]

        next_stream = cursor.execute("select name, start from streams where datetime(start) > datetime(?) order by start limit 1", (start, )).fetchone()
        if next_stream:
            end = next_stream[1]
        else:
            end = None

        print(start, end)

        params = (start, )
        qry = """select * from messages 
            where channel = '#andersonjph'
            and datetime(timestamp) >= datetime(?)"""
        if end:
            qry += "and datetime(timestamp) <= datetime(?)"
            params = (start, end)

        messages = [row for row in cursor.execute(qry, params)]
    else:
        messages = []

    messages = [{"channel": row[0], "timestamp": row[1], "name": row[2], "message": row[3]} for row in messages]
    messages_json = json.dumps(messages)
    return web.Response(text=messages_json, content_type='application/json')


async def get_streams(request):
    auth = os.environ['IRC_AUTH'].split(' ')

    username = auth[0]
    client_id = auth[1]
    token = auth[2]
    channel = auth[3].strip()

    cursor = db.cursor()

    streams = cursor.execute("select rowid, name, start from streams where `channel` = ? order by start desc", (channel, ))
    streams = [{"rowid": row[0],  "name": row[1], "start": row[2]} for row in streams]
    streams_json = json.dumps(streams)
    return web.Response(text=streams_json, content_type='application/json')

db = sqlite3.connect('ircbot.db')

app.on_startup.append(on_startup)
app.router.add_get('/messages/{stream}', get_messages)
app.router.add_get('/streams', get_streams)
web.run_app(app, port=8011)
