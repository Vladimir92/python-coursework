#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Function section
import os
# import time

import datetime, logging
from peewee import PostgresqlDatabase
from telegram.ext import Updater
# from django.utils import timezone
# from django.core.management import BaseCommand
from telegram.error import (TelegramError, Unauthorized)

from bot_models import News, User, Scale, Interest, UserInterests, NewsInterests, InternalError

# import schedule

# Logging configuration
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def publish_news(news_object, my_bot):
    # Match the user by interest and scale
    query = User.select().join(UserInterests).join(Interest).join(NewsInterests).join(News).switch(User).join(Scale) \
        .where(News.id == news_object.id,
               ((Scale.amount >= news_object.scale_from) & (Scale.amount < news_object.scale_to)))

    logger.info("Publish the news to {} users".format(query.count()))
    for user in query:
        try:
            my_bot.send_message(chat_id=user.tlg_id, text=news_object.text)
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
    unpublished_events = News.select().where(News.is_published == False)
    logger.info("Initiating publishing job\nNumber of news to send: {}".format(unpublished_events.count()))
    for news_object in unpublished_events:
        # Call the message sender from primary bot-command-file
        publish_news(news_object, my_bot)
        news_object.is_published = True
        news_object.save()


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

