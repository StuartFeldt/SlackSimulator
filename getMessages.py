from slack_simulator import Simulator
from slackclient import SlackClient
from slack_simulator.models import Comment
from slack_simulator.models import Account
from slack_simulator.database import db
from ConfigParser import SafeConfigParser
import os
import sys
import time
import datetime

sim = Simulator()
cfg = SafeConfigParser()
cfg.read("slack_simulator/slack_simulator.cfg")
token = cfg.get("slack", "token")
sc = SlackClient(token);

# get last comment date
last_comment = (
        db.query(Comment)
            .order_by(Comment.date.desc())
            .first()
    )
users = []
for account in db.query(Account):
	users.append(account.slack_user)
latest_comment_ts = sys.maxint
if(last_comment):
	latest_comment_ts = time.mktime(last_comment.date.timetuple())
channels = sc.api_call("channels.list")
for channel in channels.get('channels'):
	latest = False
	channel_id = channel['id']
	channel_name = channel['name']
	print "pulling " + channel_name
	for x in range(0,100):
		if(latest and float(latest) > float(latest_comment_ts)):
			print "Too far back..stopping"
			break

		try:
			if(latest):
				msg_results = sc.api_call("channels.history",channel=channel_id,latest=latest)
			else:
				msg_results = sc.api_call("channels.history",channel=channel_id)
		except ValueError:
			print "VALUE ERROR"
			break

		if('messages' not in msg_results or len(msg_results['messages']) == 0):
			print "Out of messages"
			break
		
		for message in msg_results['messages']:
			try:
				author = "Unknown"
				if('user' in message and message['user'].lower() not in users):
					user = sc.api_call("users.info",user=message['user'])
					account = Account(user['user']['name'], message['user'])
					account.special_class =user['user']['profile']['image_72']
					account.can_comment = not user['user']['deleted']
					account.save()
					users.append(message['user'].lower())
					author = message['user']

				if('bot_id' in message and message['bot_id'] is not None and message['bot_id'].lower() not in users):
					bot_name = message['username'] if 'username' in message else "BOT"
					account = Account(bot_name, message['bot_id'])
					if('emoji' in message['icons']):
						account.special_class = message['icons']['emoji']
					elif('image_48' in message['icons']):
						account.special_class = message['icons']['image_48']
					elif('image_72' in message['icons']):
						account.special_class = message['icons']['image_72']
					account.can_comment = True
					account.save()
					users.append(message['bot_id'].lower())
					author = message['username']
			
				if(not latest):
					latest = message['ts']
				else:
					if(message['ts'] < latest):
						latest = message['ts']
				
				comment = {}
				comment['slack_user'] = message['user'].lower()
				comment['date'] = float(message['ts'])
				comment['is_top_level'] = True
				comment['author'] = message['user']
				comment['body'] = message['text']

				score = 0
				if 'reactions' in comment:
					for reaction in comment['reactions']:
						score += reaction['count']

				comment['score'] = score
				
				commentModel = Comment(comment)
				commentModel.save()
			except Exception as e:
				pass
