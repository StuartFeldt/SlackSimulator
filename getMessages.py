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
channels_to_track = cfg.get("slack", "track_channels").split(",");
print channels_to_track

sc = SlackClient(token);

def get_channel_history(channel_id, latest):
	if(latest):
		msg_results = sc.api_call("channels.history",channel=channel_id,latest=latest)

		if msg_results["ok"] is False and msg_results["headers"]["Retry-After"]:
			delay = 60
			print msg_results
			print("Rate limited. Retrying in " + str(delay) + " seconds")
			time.sleep(delay)
			return get_channel_history(channel_id, latest)
	else:
		msg_results = sc.api_call("channels.history",channel=channel_id)
		if msg_results["ok"] is False and msg_results["headers"]["Retry-After"]:
			delay = 60
			print msg_results
			print("Rate limited. Retrying in " + str(delay) + " seconds")
			time.sleep(delay)
			return get_channel_history(channel_id, latest)
	return msg_results

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
channels = sc.api_call("channels.list", exclude_archived=1)
for channel in channels.get('channels'):
	latest = False
	channel_id = channel['id']
	channel_name = channel['name']

	if channel_name not in channels_to_track:
		continue

	print "pulling " + channel_name
	for x in range(0,1000):
		if(latest and float(latest) > float(latest_comment_ts)):
			print "Too far back..stopping"
			break

		try:
			msg_results = get_channel_history(channel_id, latest)
		except ValueError:
			print "VALUE ERROR"
			break

		if('messages' not in msg_results or len(msg_results['messages']) == 0):
			print "Out of messages"
			break
		
		print "Processing " + str(len(msg_results['messages'])) + " messages | [" + str(x) + "/1000]"
		for message in msg_results['messages']:
			if('subtype' in message and message['subtype'] == 'bot_message'):
				continue

			try:
				author = "Unknown"
				if('user' in message and message['user'].lower() not in users ):
					user = sc.api_call("users.info",user=message['user'])
					account = Account(user['user']['name'], message['user'])
					account.special_class =user['user']['profile']['image_72']
					account.can_comment = not user['user']['deleted']
					account.save()
					users.append(message['user'].lower())
					author = message['user']

				# if('bot_id' in message and message['bot_id'] is not None and message['bot_id'].lower() not in users):
				# 	bot_name = message['username'] if 'username' in message else "BOT"
				# 	account = Account(bot_name, message['bot_id'])
				# 	if('emoji' in message['icons']):
				# 		account.special_class = message['icons']['emoji']
				# 	elif('image_48' in message['icons']):
				# 		account.special_class = message['icons']['image_48']
				# 	elif('image_72' in message['icons']):
				# 		account.special_class = message['icons']['image_72']
				# 	account.can_comment = True
				# 	account.save()
				# 	users.append(message['bot_id'].lower())
				# 	author = message['username']
			
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

			except Exception, e:
				print message
				print e
				pass
