from slack_simulator import Simulator
from slackclient import SlackClient
from slack_simulator.models import Comment
from slack_simulator.models import Account
from slack_simulator.database import db
from ConfigParser import SafeConfigParser
import os
import time
import datetime

def tryToGetComment(tries):
	if tries > 3:
		print "Giving up for now"
		return

	cfg = SafeConfigParser()
	cfg.read("slack_simulator/slack_simulator.cfg")
	token = cfg.get("slack", "token")

	sim = Simulator()
	sc = SlackClient(token);

	result = sim.make_comment()
	print result
	slack_channel = cfg.get("slack", "channel")
	if(result):
		sc.api_call(
		"chat.postMessage",
		channel=slack_channel,
		text=result['comment'],
		username=result['name'],
		icon_url=result['picture']
	)
	else:
		return tryToGetComment(tries + 1)

tryToGetComment(1)