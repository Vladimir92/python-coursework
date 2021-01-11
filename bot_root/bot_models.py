import os

import uuid as uuid
from peewee import *

psql_db = PostgresqlDatabase('networking',
                             user=os.environ.get('DB_USERNAME'),
                             password=os.environ.get('DB_PASSWORD'),
                             host='127.0.0.1')


class Interest(Model):
    name = CharField(null=True)

    class Meta:
        database = psql_db
        db_table = "network_bot_interest"


class User(Model):
    tlg_id = IntegerField()
    tlg_username = CharField(max_length=125, null=True)
    first_name = CharField(max_length=125, null=True)
    last_name = CharField(max_length=125, null=True)
    referer = ForeignKeyField('self', related_name='referer_id', backref="referrers", null=True)
    is_verified = BooleanField(default=False)
    is_hidden = BooleanField(default=False)
    unique_id = UUIDField(default=uuid.uuid4, unique=True)

    class Meta:
        database = psql_db
        db_table = "network_bot_user"


class UserInterests(Model):
    user = ForeignKeyField(User)
    interest = ForeignKeyField(Interest)

    class Meta:
        database = psql_db
        db_table = "network_bot_user_interests"


class Scale(Model):
    user = ForeignKeyField(User, null=True, related_name='user_id')
    yearly_costs = IntegerField()
    salary_per_year = IntegerField()
    direct_subordinates = IntegerField()
    people_under_responsibility = IntegerField()
    managed_capital = IntegerField()
    subscribers = IntegerField()
    books_sold = IntegerField()
    public_speeches_audience = IntegerField()
    product_or_service_users = IntegerField()
    amount = IntegerField(default=0)

    class Meta:
        database = psql_db
        db_table = "network_bot_scale"


class News(Model):
    text = CharField(max_length=1024, null=True)
    is_published = BooleanField(default=False, verbose_name='already published')
    scale_from = IntegerField()
    scale_to = IntegerField()

    class Meta:
        database = psql_db
        db_table = "network_bot_news"


class NewsInterests(Model):
    news = ForeignKeyField(News)
    interest = ForeignKeyField(Interest)

    class Meta:
        database = psql_db
        db_table = "network_bot_news_interests"

