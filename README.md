## SlackSimulator
SlackSimulator is a simulator which takes all public messages from your organization's Slack instance and uses markov chains to output messages which sound similar to what a user would say.

This is based heavily on https://github.com/Deimos/SubredditSimulator

### Installation

    python setup.py install
    sqlite3 slacksimulator.db -init db.sql
Copy slack_simulator/slack_simulator.example into slack_simulator.cfg with the following filled in:

 - Slack token obtained from creating a Custom Integration Bot (https://api.slack.com/bot-users)
 - A slack channel to post to

   
### Usage

Pull comments from Slack (This can take some time depending on how large your organization is)

    python getComments.py

Post a comment if we can to Slack

    python postComment.py
These commands ideally should be ran via crons.

   
