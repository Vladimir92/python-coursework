#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Function section
import os
# import time

import datetime, logging
from peewee import PostgresqlDatabase
from telegram.ext import Updater
from telegram.error import (TelegramError, Unauthorized)

from bot_models import Novelty, User, Scale, Interest, UserInterests, NoveltyInterests, InternalError

# import schedule

# Logging configuration
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def publish_news(novelty_object, my_bot):
    # Match the user by interest and scale
    query = User.select().join(UserInterests).join(Interest).join(NoveltyInterests).join(Novelty).switch(User).join(Scale) \
        .where(Novelty.id == novelty_object.id,
               ((Scale.amount >= novelty_object.scale_from) & (Scale.amount < novelty_object.scale_to)))

    logger.info("Publish the news to {} users".format(query.count()))
    for user in query:
        try:
            my_bot.send_message(chat_id=user.tlg_id, text=novelty_object.text)
        except Unauthorized as u:
            user_msg = "{}:{} {}".format(user.username, user.first_name, user.last_name)
            logger.info("Exception occurred while sending message to user {}\n Message: {}".format(user_msg, u.message))
            continue
        except TelegramError as te:
            user_msg = "{}:{} {}".format(user.username, user.first_name, user.last_name)
            logger.info(
                "Telegram Error occurred while sending message to user {}\n Message: {}".format(user_msg, te.message))
            continue


# Method checks the Notifier table and send users the notifications about events
def news_notify(my_bot):
    unpublished_events = Novelty.select().where(Novelty.is_published == False)
    logger.info("Initiating publishing job\nNumber of news to send: {}".format(unpublished_events.count()))
    for novelty_object in unpublished_events:
        # Call the message sender from primary bot-command-file
        publish_news(novelty_object, my_bot)
        novelty_object.is_published = True
        novelty_object.save()


def main():
    psql_db = PostgresqlDatabase('networking',
                                 user=os.environ.get('DB_USERNAME'),
                                 password=os.environ.get('DB_PASSWORD'))

    try:
        psql_db.connect()
    except InternalError as px:
        print(str(px))
    # Create the EventHandler and pass it your bot's token.
    token = os.environ.get('BOT_TOKEN')
    updater = Updater(token)

    logger.info("Initiating cron news sender...")
    news_notify(updater.bot)


if __name__ == "__main__":
    main()

