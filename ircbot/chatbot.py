import sys
import irc.bot
import requests
import re
import traceback
import sqlite3
import datetime
import os


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
        
        self.db = sqlite3.connect('log.db')
        self.cursor = self.db.cursor()

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
            msg_id = 0
            user = ''

            for tag in e.tags:
                if tag['key'] == 'display-name':
                    user = tag['value']
                elif tag['key'] == 'id':
                    msg_id = tag['value']
            self.store_fanart(msg_id, msg, user)

        return

    def do_command(self, e, cmd):
        pass
        # c = self.connection
        # if cmd == "fanart":
        #     c.privmsg(self.channel, 'test weee')

    def store_fanart(self, msg_id, msg, user):
        
        for word in msg.split(' '):
            match = re.match(
                r'(?i:https?://(?:[^/:]+\.)?imgur\.com)(:\d+)?'
                r'/(?:(?P<album>a/)|(?P<gallery>gallery/))?(?P<id>\w+)',
                word
            )
            if match:
                print('Storing fanart')
                imgur = {
                    'id': match.group('id'),
                    'type': 'album' if match.group('album') else
                            'gallery' if match.group('gallery') else
                            'image',
                }
                now = datetime.datetime.now()

                self.cursor.execute("INSERT INTO fanart values (?,?,?,?,?,?)", (self.channel, imgur['id'], imgur['type'],msg_id, msg, now.strftime("%Y-%m-%d %H:%M:%S")) )
                self.db.commit()
                


def main():
    auth = os.environ['IRC_AUTH'].split(' ')

    username = auth[0]
    client_id = auth[1]
    token = auth[2]
    channel = auth[3]

    bot = TwitchBot(username, client_id, token, channel)
    bot.start()


if __name__ == "__main__":

    while True:
        try:
            main()
        except Exception:
            traceback.print_exc()
