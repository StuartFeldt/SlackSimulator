import HTMLParser
from datetime import datetime, timedelta
import pytz
import random
import re

from database import db
from models import Account


class Simulator(object):
    def __init__(self):
        self.accounts = {account.slack_user: account
            for account in db.query(Account)}

    def pick_account_to_comment(self):
        accounts = [a for a in self.accounts.values() if a.can_comment]

        # if any account hasn't commented yet, pick that one
        try:
            return next(a for a in accounts if not a.last_commented)
        except StopIteration:
            pass

        # pick an account from the 25% that commented longest ago
        accounts = sorted(accounts, key=lambda a: a.last_commented)
        num_to_keep = int(len(accounts) * 0.25)
        return random.choice(accounts[:num_to_keep])

    def make_comment(self):
        account = self.pick_account_to_comment()
        account.train_from_comments()

        return account.post_comment_on()

