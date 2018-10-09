import asyncio
import datetime
import ftplib
import glob
import io
import json
import os
import re
import sys

import discord
import socketio

from aiohttp import web

from routes import apply_routes

sio = socketio.AsyncServer()
app = web.Application()
sio.attach(app)


class VoteCounter(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.valid_message_ids = []
        self.votes = {}
        self.changed = []

        self.voter_data = {
            "total_voters": 0,
            "nontop_voters": 0,
            "top": 5
        }

        self.ready = False

    async def on_ready(self):
        print('Logged in as')
        print(self.user.name)
        print(self.user.id)
        print('------')

        await self.fetch_votes()
        self.ready = True
        await self.save_votes()

    async def fetch_votes(self):
        print("Fetching vote messages.")
        await self.wait_until_ready()

        channel = self.get_channel(492088331287527454)  # voting channel

        messages = []

        dt_from = datetime.datetime(2018, 9, 22, 20, 7, 46)
        dt_to = datetime.datetime(2018, 9, 22, 20, 19, 3)

        async for message in channel.history(after=dt_from, limit=200):
            if message.created_at >= dt_to:
                break
            # print(message.id, message.created_at, message.content)
            messages.append(message)
        self.valid_message_ids = [message.id for message in messages]

        for message in messages:
            # print(message.id)
            self.votes[message.id] = {"game": message.content,
                                      "yay": 0,
                                      "yay_rounds": [],
                                      "yay_voters": []}

            for reaction in message.reactions:
                if type(reaction.emoji) is not str:
                    continue
                if ord(reaction.emoji[0]) == 128123:  # spooky ghost
                    self.votes[message.id]['yay'] = reaction.count
                    reactors = await reaction.users().flatten()
                    self.votes[message.id]['yay_voters'] = [str(reactor) for reactor in reactors]

        for file in glob.glob("votes_round*.json"):
            match = re.match(r"(votes_round\d+).json", file)
            if match:
                olddata = json.load(open(file, 'r'))
                oldvotes = olddata['votes']
                for vote in votes:
                    for oldvote in oldvotes:
                        if oldvote['game'] == vote['game']:
                            vote["yay_rounds"].append(oldvote['votes'])

        self.changed = [id for id in self.votes]

    async def on_raw_reaction_add(self, reaction):
        if reaction.message_id in self.valid_message_ids:
            if reaction.emoji.name == '\U0001f47b':
                if reaction.message_id in self.votes:
                    self.votes[reaction.message_id]['yay'] = self.votes[reaction.message_id].get('yay', 0) + 1
                    username = self.get_user(reaction.user_id).name
                    self.votes[reaction.message_id]['yay_voters'].append(username)
                    if reaction.message_id not in self.changed:
                        self.changed.append(reaction.message_id)

    async def on_raw_reaction_remove(self, reaction):
        if reaction.message_id in self.valid_message_ids:
            if reaction.emoji.name == '\U0001f47b':
                if reaction.message_id in self.votes:
                    self.votes[reaction.message_id]['yay'] = self.votes[reaction.message_id].get('yay', 0) - 1
                    username = self.get_user(reaction.user_id).name
                    self.votes[reaction.message_id]['yay_voters'].remove(username)
                    if reaction.message_id not in self.changed:
                        self.changed.append(reaction.message_id)

    def calc_voter_data(self):
        voter_games = {}

        for vote in self.votes:
            voters = self.votes[vote]['yay_voters']
            for voter in voters:
                if voter not in voter_games:
                    voter_games[voter] = [self.votes[vote]['game'], ]
                else:
                    voter_games[voter].append(self.votes[vote]['game'])

        votes = [self.votes[id] for id in self.votes]
        votes = sorted(votes, key=lambda x: x['yay'], reverse=True)
        top = self.voter_data['top']

        top_voters = []
        for voter in voter_games:
            for vote in votes[:top]:
                if vote['game'] in voter_games[voter]:
                    top_voters.append(voter)
                    break

        self.voter_data['total_voters'] = len(voter_games)
        self.voter_data['nontop_voters'] = len(voter_games) - len(top_voters)

    async def save_votes(self):
        print("Saving Votes")
        votes = [self.votes[id] for id in self.votes]
        votes = sorted(votes, key=lambda x: x['game'].lower())
        filepath = r"votes.json"
        now = datetime.datetime.now()
        vote_data = {
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "total_voters": self.voter_data['total_voters'],
            "nontop_voters": self.voter_data['nontop_voters'],
            "votes": votes,
            "top": self.voter_data['top']
        }

        json_data = json.dumps(vote_data, indent=4, sort_keys=True)
        upload_data = io.BytesIO(json_data.encode('utf-8'))
        upload_data.seek(0)

        filename = f"votes {now.strftime('%Y-%m-%d %H%M%S')}.json"
        host, username, password = os.environ["FTP_CREDS"].split(" ")
        ftp = ftplib.FTP(host, username, password)
        ftp.storbinary(f'STOR {filename}', upload_data)
        ftp.quit()

    def generate_vote_data(self, changed_only=False):
        self.calc_voter_data()

        if changed_only:
            votes = {vote: self.votes[vote] for vote in self.changed}
        else:
            votes = self.votes

        data = {
            "total_voters": client.voter_data['total_voters'],
            "nontop_voters": client.voter_data['nontop_voters'],
            "top": client.voter_data['top'],
            "votes": votes
        }
        return data


async def send_votes(app):
    while True:
        if len(client.changed) > 0:
            await sio.emit('vote change', client.generate_vote_data(changed_only=True), namespace='/joevotes')
            client.changed = []
        await asyncio.sleep(1)


async def save_votes():
    while True:
        if client.ready:
            await client.fetch_votes()
            await client.save_votes()
        await asyncio.sleep(60)


async def start_background_tasks(app):
    app.loop.create_task(client.start(os.environ['DISCORD_TOKEN'], bot=False))
    app.loop.create_task(send_votes(app))
    app.loop.create_task(save_votes())


@sio.on('connect', namespace='/joevotes')
async def connect(sid, environ):
    await sio.emit('vote change', client.generate_vote_data(), namespace='/joevotes')


apply_routes(app)
app.on_startup.append(start_background_tasks)

client = VoteCounter()

if __name__ == '__main__':
    web.run_app(app, port=sys.argv[1])
