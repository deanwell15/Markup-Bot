import telebot
from telebot import types
import pymysql
from pymysql.cursors import DictCursor
import random
import string
import json
import redis

#Токен бота
_TOKEN = 'YOUR TOKEN FROM BOTFATHER HERE'
bot = telebot.TeleBot(_TOKEN)

r = redis.Redis(host='redis', port=6379, db=0, password='pass', charset='utf-8', errors='strict')

status = 'work'

IMAGE_FOLDER = '/uploads/'

#Функция для подключения к БД
def connect_db():
    try:
        sql = pymysql.connect(
            host="mysql",
            user="root",
            password="pass",
            db="main",
            port=3306,
            charset='utf8mb4',
            autocommit=True, #(!!!)
            cursorclass=DictCursor
        )
        return sql
    except Exception as e:
        print('Ошибка подключения к базе')
        print(e, flush=True)


#Запись в БД
def write_db(query):
    sql = connect_db()
    cursor = sql.cursor()
    cursor.execute(query)
    sql.close()

#Чтение из БД
def read_db(query):
    sql = connect_db()
    cursor = sql.cursor()
    cursor.execute(query)
    res = cursor.fetchall()
    sql.close()
    return res

def generate_creds():
    login = ''.join(random.choice(string.ascii_lowercase) for i in range(5))
    password = ''.join([str(random.randint(0, 9)) for _ in range(4)])
    q = f"""
        select * from users
        where user_name = '{login}';
    """
    res = read_db(q)
    while len(res) > 0:
        login = ''.join(random.choice(string.ascii_lowercase) for i in range(5))
        password = ''.join([str(random.randint(0, 9)) for _ in range(4)])
        q = f"""
            select * from users
            where user_name = '{login}';
        """
        res = read_db(q)

    return login, password

def check_redis(tg_id):
    global r
    if r.exists(tg_id):
        return

    r.hset(tg_id, 'logged_as', '')
    r.hset(tg_id, 'current_image', '')

def get_available_image_ids(tg_id):
    global r
    current_user_name = r.hget(tg_id, 'logged_as')
    q = f"""
                select da.image_id from image_availability da
                join users u on da.user_id = u.user_id and u.user_name = '{current_user_name.decode("utf-8")}'
                where da.user_id = u.user_id and da.image_id not in (select ud.image_id from user_images ud where ud.user_id = u.user_id);
            """
    print(q, flush=True)
    res = read_db(q)

    return [i['image_id'] for i in res]


@bot.callback_query_handler(func=lambda call: True)
def query_handler(call):
    pass


@bot.message_handler(commands=['start'])
def text_handler_cmd(message):
    chat = message.chat.id

    markup = types.ReplyKeyboardMarkup(selective=False, resize_keyboard=True)
    markup.row(types.KeyboardButton('Регистрация'))
    markup.row(types.KeyboardButton('Войти'))
    bot.send_message(chat, 'Для начала работы войдите или зарегистрируйтесь.', reply_markup=markup)


@bot.message_handler(content_types=['text'])
def text_handler_text(message):
    global status, r
    msg = message.text
    chat = message.chat.id
    tg_id = str(message.from_user.id)
    sent = False

    check_redis(tg_id)

    markup = types.ReplyKeyboardMarkup(selective=False, resize_keyboard=True)
    text = 'Вы ввели неправильную команду.'

    if status == 'login':
        status = 'work'
        creds = msg.split(' ')
        print(creds, flush=True)
        correct_cred = True
        if len(creds) == 2:
            log, pas = creds
        else:
            log, pas = '',''
            correct_cred = False

        q = f"""
            select * from users
            where user_name = '{log}' and user_password = '{pas}';
        """
        res = read_db(q)
        if len(res) == 0:
            correct_cred = False

        if correct_cred:
            r.hset(tg_id, 'logged_as', log)
            text = f'{log}, Вы успешно вошли в систему.'
            markup.row(types.KeyboardButton('Мои задания'))
            markup.row(types.KeyboardButton('Выйти'))
        else:
            text = 'Логин и пароль неправильный. Повторите вход.'

    if msg == 'Мои задания':
        text = 'Список доступных для разметки датасетов:'

        available_image_ids = get_available_image_ids(tg_id)

        if len(available_image_ids) == 0:
            text = 'В данный момент нет доступных картинок для разметки.'
            r.hset(tg_id, 'current_image', '')
            markup.row(types.KeyboardButton('Мои задания'))
            markup.row(types.KeyboardButton('Выйти'))
        else:
            #text = f"id картинок для разметки {available_image_ids}"

            image_info = read_db(f"select name, classifications from images where id = {available_image_ids[0]};")[0]
            r.hset(tg_id, 'current_image', str(available_image_ids[0]))
            classifications = image_info['classifications'].split(',')
            img = open(IMAGE_FOLDER + image_info['name'], 'rb')
            for classification in classifications:
                markup.row(types.KeyboardButton(classification))
            bot.send_photo(chat, img, reply_markup=markup)
            img.close()
            sent = True

    elif msg == 'Регистрация':
        login, password = generate_creds()

        q = f"""
            insert into users (user_name, user_password, user_type)
            values ('{login}', '{password}', 1);
        """
        write_db(q)

        user_id = read_db(f"select user_id from users where user_name = '{login}';")[0]['user_id']
        res = read_db("select id from images;")
        image_ids = [i['id'] for i in res]

        q = f"""
            insert into image_availability
            values {','.join([f"({image_id}, {user_id})" for image_id in image_ids])}
        """
        write_db(q)

        r.hset(tg_id, 'logged_as', login)

        text = f'Вы успешно зарегестрировались.\nВаш логин {login}\nВаш пароль {password}'
        markup.row(types.KeyboardButton('Мои задания'))
        markup.row(types.KeyboardButton('Выйти'))
    elif msg == 'Выйти':
        r.hset(tg_id, 'logged_as', '')
        text = 'Вы успешно вышли из системы.'
        markup.row(types.KeyboardButton('Регистрация'))
        markup.row(types.KeyboardButton('Войти'))
    elif msg == 'Войти':
        text = 'Укажите логин и пароль через пробел в одном сообщении.'
        status = 'login'
    else:
        current_image_id = r.hget(tg_id, 'current_image').decode('utf-8')
        if not current_image_id == '':

            #Записать разметку картинки
            user_name = r.hget(tg_id, 'logged_as').decode('utf-8')
            user_id = read_db(f"select user_id from users where user_name = '{user_name}';")[0]['user_id']
            q = f"""
                insert into user_images
                values (
                   {user_id},
                   {current_image_id},
                   '{msg}'
                );
            """
            write_db(q)

            #Получить новый список доступных картинок
            available_image_ids = get_available_image_ids(tg_id)

            if len(available_image_ids) == 0:
                text = 'На данный момент вы разметили все картинки.'
                r.hset(tg_id, 'current_image', '')
                markup.row(types.KeyboardButton('Мои задания'))
                markup.row(types.KeyboardButton('Выйти'))
            else:
                image_info = read_db(f"select name, classifications from images where id = {available_image_ids[0]};")[0]
                r.hset(tg_id, 'current_image', str(available_image_ids[0]))
                classifications = image_info['classifications'].split(',')
                img = open(IMAGE_FOLDER + image_info['name'], 'rb')
                for classification in classifications:
                    markup.row(types.KeyboardButton(classification))
                bot.send_photo(chat, img, reply_markup=markup)
                img.close()
                sent = True


    if not sent:
        bot.send_message(chat, text, reply_markup=markup)


bot.polling(none_stop=True)
