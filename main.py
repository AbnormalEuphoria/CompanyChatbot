from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram.types import ContentType, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import random
import re
import json
import logging
import psycopg2
import secrets
import string
import requests
from requests.auth import HTTPBasicAuth
import spacy


ADMIN_TELEGRAM_ID = 389486963

user_states = {}

nlp = spacy.load("en_core_web_sm")

conn = psycopg2.connect(
    dbname="postgres",
    user="postgres",
    password="1234",
    host="localhost"
)
cursor = conn.cursor()

resources = {
    "login": {
        "keywords": ["логин", "вход", "авторизация", "аутентификация"],
        "url": "https://helpdesk.example.com/login-issues"
    },
    "network": {
        "keywords": ["сеть", "подключение", "wifi", "интернет"],
        "url": "https://helpdesk.example.com/network-issues"
    },
    "email": {
        "keywords": ["email", "e-mail", "inbox", "smtp", "outlook"],
        "url": "https://helpdesk.example.com/email-issues"
    }
}

# def create_jira_issue(summary, description, project_key, issue_type, jira_url, jira_user, api_token):
#     url = f"{jira_url}/rest/api/3/issue"
#     headers = {
#         "Accept": "application/json",
#         "Content-Type": "application/json"
#     }
#     auth = HTTPBasicAuth(jira_user, api_token)
#     json = {
#         "fields": {
#             "project":
#             {
#                 "key": project_key
#             },
#             "summary": summary,
#             "description": description,
#             "issuetype": {
#                 "name": issue_type
#             }
#         }
#     }
#
#     response = requests.post(url, json=json, headers=headers, auth=auth)
#     if response.status_code == 201:
#         return f"Successfully created Issue ID: {response.json()['id']}"
#     else:
#         return f"Failed to create issue: {response.status_code} {response.text}"

def verify_secret_phrase(user_id, provided_phrase):
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT secret_phrase FROM users WHERE telegram_id = %s", (user_id,))
        result = cursor.fetchone()
        if result and result[0] == provided_phrase:
            return True
        return False
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def find_resource_nlp(message):
    doc = nlp(message.lower())
    for token in doc:
        for category, info in resources.items():
            if token.lemma_ in info["keywords"]:
                return info["url"]
    return "К сожалению, я не смог найти информацию по вашему запросу. Пожалуйста, свяжитесь со службой технической поддержки."


def create_connection():
    """Establishes a database connection and returns the connection object."""
    return psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password="1234",
        host="localhost"
    )

def is_verified_user(telegram_id):
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT is_verified FROM users WHERE telegram_id = %s", (telegram_id,))
        result = cursor.fetchone()
        return result and result[0]
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def fetch_name(telegram_id):
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM users WHERE telegram_id = %s", (telegram_id,))
        result = cursor.fetchone()
        return result[0]
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_service_keyboard():
    """Creates an inline keyboard with service options."""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Восстановление доступа", callback_data='access_restoration'))
    keyboard.add(InlineKeyboardButton("Запрос на изменение роли", callback_data='role_management'))
    keyboard.add(InlineKeyboardButton("Справочная информация", callback_data='general_help'))
    return keyboard


logging.basicConfig(filename='chat.log', level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

bot = Bot(token='6580173132:AAH2WCaDWJwvQyVgrV1b7DGmBRS-T6nvx40')
dp = Dispatcher(bot)

def set_randomized_password(telegram_id):
    alphabet = string.ascii_letters + string.digits
    password = ''.join(secrets.choice(alphabet) for i in range(20))
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET password = %s WHERE telegram_id = %s", (password, telegram_id,))
        conn.commit()

        return f"Пароль изменен на временный - {password}. Пожалуйста, измените его при следующем входе в систему"
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        cursor.close()
        conn.close()



@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    log_msg = f"User {message.from_user.id}: {message.text}"
    logging.info("Received message: %s", log_msg)
    if is_verified_user(message.from_user.id):
        response_text = f"Здравствуйте, {fetch_name(message.from_user.id)}! Вы подтвержденный пользователь, как я могу вам помочь?"
        await message.answer(response_text, reply_markup=get_service_keyboard())
    else:
        await message.answer("Вы не являетесь подтвержденным пользователем.")
        logging.info("Unauthorized access to Chatbot")

@dp.message_handler()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    log_msg = f"User {message.from_user.id}: {message.text}"
    logging.info("Received message: %s", log_msg)
    if is_verified_user(message.from_user.id):
        pass
    else:
        await message.answer("У вас нет доступа к данному сервису.")
        logging.info("Unauthorized access to Chatbot")

    if user_id in user_states and user_states[user_id] == 'awaiting_secret_phrase':
        provided_phrase = message.text
        if verify_secret_phrase(user_id, provided_phrase):
            response = set_randomized_password(message.from_user.id)
            await bot.send_message(message.from_user.id, response, reply_markup=get_service_keyboard())
        else:
            await message.answer("Неверная секретная фраза. Пожалуйста, попробуйте еще раз или свяжитесь со службой технической поддержки.")
        user_states[user_id] = None

    if user_id in user_states and user_states[user_id] == 'awaiting_role_description':
        user_name = message.from_user.full_name
        description = message.text
        admin_message = f"Пользователь {user_name} (ID: {user_id}) отправил запрос на получение доступа: '{description}'"


        keyboard = InlineKeyboardMarkup()
        approve_button = InlineKeyboardButton("Принять", callback_data=f"approve_{user_id}")
        disapprove_button = InlineKeyboardButton("Отклонить", callback_data=f"disapprove_{user_id}")
        keyboard.add(approve_button, disapprove_button)

        await bot.send_message(ADMIN_TELEGRAM_ID, admin_message, reply_markup=keyboard)
        await message.answer("Ваш запрос на изменение доступа был направлен на рассмотрение.", reply_markup=get_service_keyboard())
        user_states[user_id] = None
    if user_id in user_states and user_states[user_id] == 'awaiting_general_help_description':


        resource_link = find_resource_nlp(message.text)
        await message.answer(f"{resource_link}", reply_markup=get_service_keyboard())

        user_states[user_id] = None

@dp.callback_query_handler(lambda c: c.data.startswith('access_restoration'))
async def process_access_restoration(callback_query: types.CallbackQuery):
    if is_verified_user(callback_query.from_user.id):
        user_id = callback_query.from_user.id
        user_states[user_id] = 'awaiting_secret_phrase'
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(callback_query.from_user.id, "Пожалуйста, введите секретную фразу для смены пароля.")

    else:
        await bot.send_message(callback_query.from_user.id, "У вас нет доступа к данному сервису.")
        logging.info("Unauthorized access to Chatbot")


@dp.callback_query_handler(lambda c: c.data.startswith('general_help'))
async def process_general_help(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_states[user_id] = 'awaiting_general_help_description'
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "Пожалуйста, опишите ваш вопрос.")


# @dp.callback_query_handler(lambda c: c.data == 'role_management')
# async def process_role_management(callback_query: types.CallbackQuery):
#     user_id = callback_query.from_user.id
#     user_name = callback_query.from_user.full_name  # Get the user's full name to include in the admin message
#
#     keyboard = InlineKeyboardMarkup(row_width=2)
#     approve_button = InlineKeyboardButton("Approve", callback_data=f"approve_{user_id}")
#     disapprove_button = InlineKeyboardButton("Disapprove", callback_data=f"disapprove_{user_id}")
#     keyboard.add(approve_button, disapprove_button)
#
#     # Notify the admin
#     admin_message = f"User {user_name} (ID: {user_id}) has requested role management."
#     await bot.send_message(ADMIN_TELEGRAM_ID, admin_message, reply_markup=keyboard)
#
#     # Notify the user that their request is being processed
#     await bot.answer_callback_query(callback_query.id)
#     await bot.send_message(callback_query.from_user.id, "Your request for role management has been forwarded to an admin. You will be notified upon approval.")

@dp.callback_query_handler(lambda c: c.data == 'role_management')
async def process_role_management(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_states[user_id] = 'awaiting_role_description'
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "Пожалуйста, опишите ваш запрос на изменение роли.")

@dp.callback_query_handler(lambda c: c.data.startswith('approve_'))
async def approve_request(callback_query: types.CallbackQuery):

    user_id = callback_query.data.split('_')[1]
    await bot.send_message(user_id, "Ваш запрос был одобрен администратором", reply_markup=get_service_keyboard())
    await bot.answer_callback_query(callback_query.id, "Запрос одобрен.")
    await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)

@dp.callback_query_handler(lambda c: c.data.startswith('disapprove_'))
async def disapprove_request(callback_query: types.CallbackQuery):
    user_id = callback_query.data.split('_')[1]
    await bot.send_message(user_id, "Ваш запрос был отклонен администратором.", reply_markup=get_service_keyboard())
    await bot.answer_callback_query(callback_query.id, "Запрос отклонен.")
    await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)

# @dp.message_handler()  # Assuming this handler catches follow-up messages for simplicity
# async def handle_message(message: types.Message):ЫЫ
#     resource_link = find_resource_nlp(message.text)
#     await message.answer(resource_link)Ы

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
