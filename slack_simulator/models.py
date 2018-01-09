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

MAX_OVERLAP_RATIO =.5
MAX_OVERLAP_TOTAL = 10
DEFAULT_TRIES = 10000

class SlackSimulatorText(markovify.Text):
    html_parser = HTMLParser.HTMLParser()

    def test_sentence_input(self, sentence):
        return True

    def _prepare_text(self, text):
        text = self.html_parser.unescape(text)
        text = text.strip()
        if not text.endswith((".", "?", "!")):
            text += "."

        return text

    def sentence_split(self, text):
        # split everything up by newlines, prepare them, and join back together
        lines = text.splitlines()
        text = " ".join([self._prepare_text(line)
            for line in lines if line.strip()])

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

    @property
    def session(self):
        if not hasattr(self, "_session"):
            self._session = praw.Reddit(Settings["user agent"])
            self._session.login(
                self.name, Settings["password"], disable_warning=True)

        return self._session

    @property
    def is_able_to_submit(self):
        captcha_exempt = self.comment_karma > 5 or self.link_karma > 2
        return self.can_submit and captcha_exempt

    def get_comments_from_site(self, limit=None, store_in_db=True):
        slack_user = self.session.get_slack_user(self.slack_user)

        # get the newest comment we've previously seen as a stopping point
        last_comment = (
            db.query(Comment)
                .filter_by(slack_user=self.slack_user)
                .order_by(Comment.date.desc())
                .first()
        )

        seen_ids = set()
        comments = []

        for comment in slack_user.get_comments(limit=limit):
            comment = Comment(comment)

            if last_comment:
                if (comment.id == last_comment.id or 
                        comment.date <= last_comment.date):
                    break

            # somehow there are occasionally duplicates - skip over them
            if comment.id in seen_ids:
                continue
            seen_ids.add(comment.id)

            comments.append(comment)
            if store_in_db:
                db.add(comment)

        if store_in_db:
            db.commit()
        return comments

    def should_include_comment(self, comment):
        return True

    def get_comments_for_training(self, limit=None):
        comments = (db.query(Comment)
            .filter_by(slack_user=self.slack_user)
            .order_by(func.random())
            .limit(10000)
        )
        valid_comments = [comment for comment in comments
            if self.should_include_comment(comment)]
        return valid_comments

    def train_from_comments(self, get_new_comments=False):
        if get_new_comments:
            self.get_comments_from_site()

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

        self.comment_model = SlackSimulatorText("\n".join(valid_comments), state_size=state_size)

    def make_comment_sentence(self):
        # self.chain = self.comment_model
        return self.comment_model.make_sentence(tries=10000,
            max_overlap_total=MAX_OVERLAP_TOTAL,
            max_overlap_ratio=MAX_OVERLAP_RATIO)

    def build_comment(self):
        comment = ""
        while True:
            # For each sentence, check how close to the average comment length
            # we are, then use the remaining percentage as the chance of
            # adding another sentence. For example, if we're at 70% of the
            # average comment length, there will be a 30% chance of adding
            # another sentence. We're also adding a fixed 10% on top of that
            # just to increase the length a little, and have some chance of
            # continuing once we're past the average.
            portion_done = len(comment) / float(self.avg_comment_len)
            continue_chance = 1.0 - portion_done
            continue_chance = max(0, continue_chance)
            continue_chance += 0.1
            if random.random() > continue_chance:
                break

            new_sentence = self.make_comment_sentence()
            comment += " " + new_sentence

        comment = comment.strip()
        
        return comment

    def make_selftext_sentence(self):
        if self.selftext_model:
            return self.selftext_model.make_sentence(tries=10000,
                max_overlap_total=MAX_OVERLAP_TOTAL,
                max_overlap_ratio=MAX_OVERLAP_RATIO)
        else:
            return None

    def post_comment_on(self):
        name = (db.query(Account)
                .filter_by(slack_user=self.slack_user)
                .first())        
        print name.name
        try:
            comment = self.build_comment()
        except Exception:
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

    id = Column(String(10))
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
        db.commit()

    def __init__(self, comment):
        self.id = comment['id']
        self.slack_user = comment['slack_user']
        self.date = datetime.utcfromtimestamp(comment['date'])
        if comment['author']:
            self.author = comment['author']
        else:
            self.author = "[deleted]"
        self.body = comment['body']
        self.score = comment['score']
