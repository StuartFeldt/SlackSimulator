import HTMLParser
from datetime import datetime
import random

import markovify
import praw
import pytz
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql.expression import func

from database import Base, JSONSerialized, db

MAX_OVERLAP_RATIO = .33
MAX_OVERLAP_TOTAL =  7
DEFAULT_TRIES = 1000000

class SlackSimulatorText(markovify.Text):
    html_parser = HTMLParser.HTMLParser()

    def _prepare_text(self, text):
        text = text.decode("utf8")
        text = self.html_parser.unescape(text)
        # text = text.strip()
        if not text.endswith((".", "?", "!")):
            text += ". "
        return text

    def sentence_split(self, text):
        # split everything up by newlines, prepare them, and join back together
        lines = text.splitlines()
        text = ""
        for line in lines:
            text = text + self._prepare_text(line)

        return markovify.split_into_sentences(text)


class Account(Base):
    __tablename__ = "accounts"
    name = Column(String(20), primary_key=True)
    slack_user = Column(String(21))
    special_class = Column(String(50))
    added = Column(DateTime(timezone=True))
    can_submit = Column(Boolean, default=False)
    num_submissions = Column(Integer, default=0)
    last_submitted = Column(DateTime(timezone=True))
    can_comment = Column(Boolean, default=True)
    num_comments = Column(Integer, default=0)
    last_commented = Column(DateTime(timezone=True))


    def save(self):
        db.add(self)
        db.commit()

    def __init__(self, name, slack_user, can_comment=True, can_submit=False):
        self.name = name
        self.slack_user = slack_user.lower()
        self.can_comment = can_comment
        self.can_submit = can_submit
        self.added = datetime.now(pytz.utc)


    def get_comments_for_training(self, limit=None):
        comments = (db.query(Comment)
            .filter_by(slack_user=self.slack_user)
            .order_by(func.random())
            .limit(10000)
        )
        
        return comments

    def train_from_comments(self):

        comments = []
        for comment in self.get_comments_for_training():
            comments.append(comment.body)

        all_length = 0
        valid_comments = []
        for c in comments:
            if(isinstance(c, basestring)):
                all_length+=len(str(c.encode('utf-8').strip()))
                valid_comments.append(c)
        if(len(valid_comments) == 0):
            valid_comments.append('')
        self.avg_comment_len = len(valid_comments) / float(len(valid_comments))
        self.avg_comment_len = min(250, self.avg_comment_len)
        if self.avg_comment_len >= 140:
            state_size = 3
        else:
            state_size = 2
        print str(len(valid_comments)) + " valid comments"
        all_comments = ""
        for c in valid_comments:
            all_comments = all_comments + "\n" + c

        self.comment_model = SlackSimulatorText(all_comments.encode('utf-8').strip())

    def make_comment_sentence(self):
        # self.chain = self.comment_model
        return self.comment_model.make_sentence(tries=10000,
            max_overlap_total=MAX_OVERLAP_TOTAL,
            max_overlap_ratio=MAX_OVERLAP_RATIO)

    def build_comment(self):
        comment = ""
        tries = 0
        while True:
            print "TRYING"
            # For each sentence, check how close to the average comment length
            # we are, then use the remaining percentage as the chance of
            # adding another sentence. For example, if we're at 70% of the
            # average comment length, there will be a 30% chance of adding
            # another sentence. We're also adding a fixed 10% on top of that
            # just to increase the length a little, and have some chance of
            # continuing once we're past the average.
            tries = tries + 1
            portion_done = len(comment) / float(self.avg_comment_len)
            continue_chance = 1.0 - portion_done
            continue_chance = max(0, continue_chance)
            continue_chance += 0.1
            random_value = random.random()
            if  random_value > continue_chance:
                break

            if  tries > 10:
                return False
                break

            new_sentence = self.make_comment_sentence()

            if not new_sentence:
                continue
                
            comment += " " + new_sentence

        comment = comment.strip()
        
        return comment

    def post_comment_on(self):
        name = (db.query(Account)
                .filter_by(slack_user=self.slack_user)
                .first())        
        print name.name
        try:
            comment = self.build_comment()
        except Exception as e:
            print e
            self.last_commented = datetime.now()
            self.num_comments += 1
            db.add(self)
            db.commit()
            return False

        # update the database
        self.last_commented = datetime.now()
        self.num_comments += 1
        db.add(self)
        db.commit()
        return {'name': name.name, 'comment': comment, 'picture': name.special_class}

class Comment(Base):
    __tablename__ = "comments"

    slack_user = Column(String(21))
    date = Column(DateTime)
    author = Column(String(20))
    body = Column(Text, primary_key=True)
    score = Column(Integer)

    __table_args__ = (
        Index("ix_comment_slack_user_date", "slack_user", "date"),
    )

    def save(self):
        db.add(self)
        try:
            db.commit()
        except Exception as ex:
            db.rollback()
            db.add(self)
            db.commit()

    def __init__(self, comment):
        self.slack_user = comment['slack_user']
        self.date = datetime.utcfromtimestamp(comment['date'])
        if comment['author']:
            self.author = comment['author']
        else:
            self.author = "[deleted]"
        self.body = comment['body']
        self.score = comment['score']
