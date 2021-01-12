#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
import urllib.parse

from bot_models import Novelty, User, Scale, Interest, UserInterests, NoveltyInterests, InternalError, psql_db
from peewee import PostgresqlDatabase
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, ConversationHandler, CallbackQueryHandler, MessageHandler, Filters

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)
YEARLY_COSTS, YEARLY_SALARY, DIRECT_SUBORDINATES, PEOPLE_RESPONSIBLE, MANAGED_CAPITAL, SUBSCRIBERS, \
BOOKS_SOLD, AUDIENCE, PRODUCT_USERS = range(9)

BOT_NAME = "YourNetworkBot"

vk_url = "https://vk.com/share.php?"
sharing_url_vk = {
    "url": "",
}
fb_url = "https://www.facebook.com/sharer/sharer.php?"
sharing_url_fb = {
    "u": "",
}


def start(bot, update):
    user = update.message.from_user
    logger.info("Report command of %s: %s", user.first_name, update.message.text)
    # Parsing out the referral UUID
    ref_id = None
    if len(update.message.text.split(" ")) > 1:
        ref_id = update.message.text.split(" ")[1]
    # Registering the user if its new one
    # logger.info("Starting user register with ref_id = {}".format(ref_id))
    get_or_register_user(user, ref_id)
    update.message.reply_text(
        'Приветствую, {}!\nЯ бот созданный чтобы помогать интересным людям находить других интересных людей. '
        'Чтобы я мог тебе помочь искать интересных людей, мне нужно знать твой масштаб личности.'
        '\nМасштаб личности - это показатель твоего влияния на других людей/общество/страну в целом\n\n'
            .format(user.first_name if user.first_name else user.username))
    # Sending the message with Scale calculation button
    # For now skipping the users with calculated scale
    create_menu_message(bot, update)


def get_or_register_user(user, ref_id=None):
    ref_user = None
    if ref_id:
        query = User.select().where(User.unique_id == ref_id)
        if query.exists():
            ref_user = query.get()
    # logger.info("In register user, ref_id is {} and user found is {}".format(ref_id, ref_user))

    # Register in DB if not exist, putting the referrer id if provided
    if not User.select().where(User.tlg_id == user.id).exists():
        # logger.info("Putting ref_user id {} to user {}".format(ref_user, user.first_name))
        user_object = User.create(tlg_id=user.id,
                                  tlg_username=user.username,
                                  first_name=user.first_name,
                                  last_name=user.last_name,
                                  referer=ref_user)
    else:
        user_object = User.select().where(User.tlg_id == user.id).get()
    return user_object


# Parameter is Telegram user from Update
def get_user_scale(user):
    if not Scale.select().join(User).where(User.tlg_id == user.id).exists():
        user = get_or_register_user(user)
        scale = Scale.create(user=user, amount=0)
    else:
        scale = Scale.select().join(User).where(User.tlg_id == user.id).get()
    return scale


# Function displays initial message in scale-calculation dialogue
def scale_initial(bot, update):
    query = update.callback_query
    query.edit_message_text("Начинаем подсчет масштаба вашей личности.\nЕсли хотите прекратить, нажмите /interrupt\n")
    query.message.reply_text("Укажите свои затраты в год (целое число в рублях).\n"
                             "Сколько личных денег вы тратите за год. Здесь пишется сумма всех ваших ЛИЧНЫХ расходов. "
                             "Расходы вашего бизнеса здесь не учитываются.")
    return YEARLY_COSTS


def interrupt(bot, update):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text("Операция отменена")
    create_menu_message(bot, update)
    return ConversationHandler.END


# Method appends to provided TelegramKeyboard the Social buttons from constants
def appendSocialButtons(keyboard, url):
    sharing_url_fb["u"] = url
    keyboard.append(
        [InlineKeyboardButton("Поделиться в Facebook 🔗", url=fb_url + urllib.parse.urlencode(sharing_url_fb))])

    sharing_url_vk["url"] = url
    keyboard.append(
        [InlineKeyboardButton("Поделиться в VK 🔗", url=vk_url + urllib.parse.urlencode(sharing_url_vk))])

    return keyboard


# Function displays main bot working MENU
# 1st is Scale and interests
# 2nd is Referral system
def create_menu_message(bot, update, is_callback=False):
    if is_callback:
        user = update.from_user
    else:
        user = update.message.from_user
    user_object = get_or_register_user(user)
    keyboard = []
    # Check, if the user have not calculate scale - display only one option
    if get_user_scale(user).amount <= 0:
        keyboard.append([InlineKeyboardButton("Рассчитать масштаб личности", callback_data="scale_processing_start")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = "Хочешь узнать на сколько ты масштабная личность и получить доступ к самым интересным для тебя " \
                  "событиям? "
        update.message.reply_text(message, reply_markup=reply_markup)
        return
    # Adding the ability to recalculate scale at any time
    query = Scale.select().join(User).where(User.tlg_id == user.id)
    message = "{}, ваши данные по нетворкинг сети:\n" \
              "Масштаб вашей личности: {}\n".format(user.first_name if user.first_name else user.username,
                                                    query.get().amount)
    keyboard.append([InlineKeyboardButton("Пересчитать масштаб личности", callback_data="scale_processing_start")])
    # Referral system data to message append
    Referrer = User.alias()
    query = User.select().join(Referrer, on=(Referrer.referer == User.id)).where(User.tlg_id == user.id)
    ref_link = "https://t.me/{bot_name}?start={lnk}".format(bot_name=BOT_NAME, lnk=user_object.unique_id)
    message = "{}\nПриглашено человек по реферальной системе: {}" \
              "\nВаша реферальная ссылка: {}\n".format(message, query.count(), ref_link)

    # If the user does not have selected interests, show him the invitation to fill them
    if Interest.select().join(UserInterests).join(User).where(User.tlg_id == user.id).count() < 1:
        message = "{}\nЧтобы получать наиболее интересные для вас новости, укажите ваши интересы".format(message)
        keyboard.append([InlineKeyboardButton("Указать интересы", callback_data="interests_set")])
        keyboard = appendSocialButtons(keyboard, ref_link)
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(message, reply_markup=reply_markup)
        return
    query = User.select().join(UserInterests).join(Interest).where(User.tlg_id == user.id)
    message = "{}\nУказано {} интересов для уточнения новостей".format(message, query.count())
    keyboard.append([InlineKeyboardButton("Уточнить интересы", callback_data="interests_set")])
    keyboard = appendSocialButtons(keyboard, ref_link)
    # Final reply
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(message, reply_markup=reply_markup)


# Function puts all possible interests to callback buttons and return them to user
def interests_show(bot, update):
    query = update.callback_query
    user = query.from_user
    keyboard = []
    for interest in Interest.select():
        if User.select().join(UserInterests).join(Interest).where(User.tlg_id == user.id,
                                                                  Interest.name == interest.name).exists():
            prefix = "✅ "
        else:
            prefix = ""
        keyboard.append([InlineKeyboardButton(prefix + interest.name, callback_data="interest_{}".format(interest.id))])
    keyboard.append([InlineKeyboardButton("Готово", callback_data="interests_finish")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text("Отметьте ваши интересы.\nДля заверешения нажмите \"Готово\"", reply_markup=reply_markup)


def interests_process(bot, update):
    query = update.callback_query
    interest_id = query.data.split("_")[1]
    user_object = get_or_register_user(query.from_user)
    user = query.from_user
    target_interest = Interest.get(id=interest_id)
    keyboard = []

    if not User.select().join(UserInterests).join(Interest).where(User.tlg_id == user.id,
                                                                  Interest.name == target_interest.name).exists():
        UserInterests.create(user=user_object, interest=target_interest)
    else:
        ui = UserInterests.get(UserInterests.user == user_object, UserInterests.interest == target_interest)
        ui.delete_instance()

    for interest in Interest.select():
        if User.select().join(UserInterests).join(Interest).where(User.tlg_id == user.id,
                                                                  Interest.name == interest.name).exists():
            prefix = "✅ "
        else:
            prefix = ""
        keyboard.append([InlineKeyboardButton(prefix + interest.name, callback_data="interest_{}".format(interest.id))])
    keyboard.append([InlineKeyboardButton("Готово", callback_data="interests_finish")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_reply_markup(reply_markup=reply_markup)
    query.answer("Интерес обновлен ✅")


def interests_finish(bot, update):
    query = update.callback_query
    query.edit_message_text("Выбор интересов завершен")
    query.answer("Новые интересы заданы ✅")
    create_menu_message(bot, query, is_callback=True)


# Error handlers also receive the raised TelegramError object in error.
def error(bot, update, error):
    """Log Errors caused by Updates."""
    logger.error('Update "%s" caused error "%s"', update, error)


# Process the entered yearly costs and display the
def process_cost_and_ask_salary(bot, update):
    text = update.message.text
    user = update.message.from_user
    try:
        amount = int(text)
        scale = get_user_scale(user)
        scale.yearly_costs = amount
        # Resetting the scale for safe purposes
        scale.amount = 0
        scale.save()
        update.message.reply_text("Сколько з/п платите за год (Только для собственников бизнеса, целое число в "
                                  "рублях).\n"
                                  "Суммарное количество заработных плат, которые вы выплатили за последние 12 месяцев.")
        return YEARLY_SALARY
    except ValueError:
        update.message.reply_text("Укажите целое число без букв и знаков.")
        return YEARLY_COSTS


def process_salary_and_ask_subordinates(bot, update):
    text = update.message.text
    user = update.message.from_user
    try:
        amount = int(text)
        scale = get_user_scale(user)
        scale.salary_per_year = amount
        scale.save()
        update.message.reply_text("Сколько человек у вас в прямом подчинении?"
                                  "\nЗдесь учитываются только сотрудники в прямом подчинении. Собственники бизнеса в "
                                  "этом разделе указывают не всех своих сотрудников, а только тех, "
                                  "с кем непосредственно взаимодействуют")
        return DIRECT_SUBORDINATES
    except ValueError:
        update.message.reply_text("Укажите целое число без букв и знаков.")
        return YEARLY_SALARY


def process_subordinates_and_ask_people_inresponsiblity(bot, update):
    text = update.message.text
    user = update.message.from_user
    try:
        amount = int(text)
        scale = get_user_scale(user)
        scale.direct_subordinates = amount
        scale.save()
        update.message.reply_text("Сколько человек у вас в зоне ответственности?"
                                  "\nЕсли ваша деятельность связана с обеспечением деятельности других людей ("
                                  "например: учителя, чиновники, контролирующие органы и др), указываете сколько "
                                  "всего человек в зоне вашего влияния/ответственности")
        return PEOPLE_RESPONSIBLE
    except ValueError:
        update.message.reply_text("Укажите целое число без букв и знаков.")
        return DIRECT_SUBORDINATES


def process_peopleinresponse_and_ask_managed_sums(bot, update):
    text = update.message.text
    user = update.message.from_user
    try:
        amount = int(text)
        scale = get_user_scale(user)
        scale.people_under_responsibility = amount
        scale.save()
        update.message.reply_text("Какими суммами вы управляете?"
                                  "\nЕсли ваша деятельность связана с управлением чужими активами, то в этой графе "
                                  "указываете сумму за год, которую распределяете. Личные траты и траты вашего "
                                  "бизнеса тут не учитываются")
        return MANAGED_CAPITAL
    except ValueError:
        update.message.reply_text("Укажите целое число без букв и знаков.")
        return PEOPLE_RESPONSIBLE


def process_sums_and_ask_subscribers(bot, update):
    text = update.message.text
    user = update.message.from_user
    try:
        amount = int(text)
        scale = get_user_scale(user)
        scale.managed_capital = amount
        scale.save()
        update.message.reply_text("Сколько у вас подписчиков в соцсетях?"
                                  "\nУкажите суммарное количество всех подписчиков, по всем социальным сетям")
        return SUBSCRIBERS
    except ValueError:
        update.message.reply_text("Укажите целое число без букв и знаков.")
        return MANAGED_CAPITAL


def process_subscribers_and_ask_books_sold(bot, update):
    text = update.message.text
    user = update.message.from_user
    try:
        amount = int(text)
        scale = get_user_scale(user)
        scale.subscribers = amount
        scale.save()
        update.message.reply_text("Сколько экземпляров ваших книг продано?"
                                  "\nУкажите количество проданных экземпляров за последние 12 месяцев")
        return BOOKS_SOLD
    except ValueError:
        update.message.reply_text("Укажите целое число без букв и знаков.")
        return SUBSCRIBERS


def process_books_and_ask_audience(bot, update):
    text = update.message.text
    user = update.message.from_user
    try:
        amount = int(text)
        scale = get_user_scale(user)
        scale.books_sold = amount
        scale.save()
        update.message.reply_text("Суммарная аудитория ваших публичных выступлений за год?"
                                  "\nСчитается вся аудитория, как живых выступлений, так и вебинаров")
        return AUDIENCE
    except ValueError:
        update.message.reply_text("Укажите целое число без букв и знаков.")
        return BOOKS_SOLD


def process_audience_and_ask_products(bot, update):
    text = update.message.text
    user = update.message.from_user
    try:
        amount = int(text)
        scale = get_user_scale(user)
        scale.public_speeches_audience = amount
        scale.save()
        update.message.reply_text("Сколько человек пользуются Вашим товаром или услугой?"
                                  "\nВопрос только для собственников бизнеса. Если бизнес товарный, "
                                  "то заполняется только если свое производство. Если бизнес продает услугу, "
                                  "то считаются все клиенты за последние 12 месяцев."
                                  "\nЕсли вы не владеете бизнесом, поставьте 0")
        return PRODUCT_USERS
    except ValueError:
        update.message.reply_text("Укажите целое число без букв и знаков.")
        return AUDIENCE


def process_products_and_finalize(bot, update):
    text = update.message.text
    user = update.message.from_user
    try:
        amount = int(text)
        scale = get_user_scale(user)
        scale.product_or_service_users = amount
        # Random var, while we do not have formula
        scale.amount = scale_calc(scale)
        scale.save()
        update.message.reply_text("Спасибо за время участие. Масштаб вашей личности: {}".format(scale.amount))
        create_menu_message(bot, update)
        return ConversationHandler.END
    except ValueError:
        update.message.reply_text("Укажите целое число без букв и знаков.")
        return PRODUCT_USERS


# Function calculates
def scale_calc(scale):
    amount_scale = scale.yearly_costs + (scale.salary_per_year / 2) + (scale.direct_subordinates * 12000)
    amount_scale += (scale.people_under_responsibility * 40) + (scale.managed_capital * 0.05) + \
                    (scale.subscribers * 400)
    amount_scale += (scale.books_sold * 1200) + (scale.public_speeches_audience * 1200) + \
                    (scale.product_or_service_users * 40)
    amount_scale /= 10000
    return round(amount_scale)


def main():
    try:
        psql_db.connect()
    except InternalError as px:
        print(str(px))
    # Create the EventHandler and pass it your bot's token.
    token = os.environ.get('BOT_TOKEN')
    # REQUEST_KWARGS={
    #     'proxy_url': 'http://my-proxy:8080/',
    # }
    try:
        # Add request_kwargs=REQUEST_KWARGS to Updater invoke to set proxy params
        updater = Updater(token)
    except ValueError as err:
        print("Bot token error!", err, ". Exiting now...")
        exit(1)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Log all errors
    dp.add_error_handler(error)

    # Adding event handlers
    dp.add_handler(CommandHandler("start", start))
    # Handler for scale calculation dialogue
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(scale_initial, pattern="^scale_processing_start$")],
        states={
            YEARLY_COSTS: [MessageHandler(Filters.text, process_cost_and_ask_salary)],
            YEARLY_SALARY: [MessageHandler(Filters.text, process_salary_and_ask_subordinates)],
            DIRECT_SUBORDINATES: [MessageHandler(Filters.text, process_subordinates_and_ask_people_inresponsiblity)],
            PEOPLE_RESPONSIBLE: [MessageHandler(Filters.text, process_peopleinresponse_and_ask_managed_sums)],
            MANAGED_CAPITAL: [MessageHandler(Filters.text, process_sums_and_ask_subscribers)],
            SUBSCRIBERS: [MessageHandler(Filters.text, process_subscribers_and_ask_books_sold)],
            BOOKS_SOLD: [MessageHandler(Filters.text, process_books_and_ask_audience)],
            AUDIENCE: [MessageHandler(Filters.text, process_audience_and_ask_products)],
            PRODUCT_USERS: [MessageHandler(Filters.text, process_products_and_finalize)]
        },
        fallbacks=[CommandHandler('interrupt', interrupt)],
        allow_reentry=True
    )
    dp.add_handler(conv_handler)
    dp.add_handler(CallbackQueryHandler(interests_show, pattern="^interests_set$"))
    dp.add_handler(CallbackQueryHandler(interests_process, pattern="^interest_\d{1,4}$"))
    dp.add_handler(CallbackQueryHandler(interests_finish, pattern="^interests_finish$"))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()

