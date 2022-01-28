import os
from flask import Flask, render_template, request, redirect, url_for
import pymysql
from pymysql.cursors import DictCursor
import time

_PORT = 5000
_HOST = "0.0.0.0"
UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'txt', 'png', 'jpg', 'jpeg'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
#'mysql://root:pass@mysql/main'


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

@app.route("/login", methods=['GET', 'POST'])
def login():
    message = ''
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        q = f"""
        select * from users
        where user_name = '{username}' and user_password = '{password}';
        """
        res = read_db(q)
        if len(res) > 0:
            if res[0]['user_type'] == 2:
                return redirect(url_for('upload', user_id=res[0]['user_id']))
            else:
                print('SIMPLE USER RESTRICTED', flush=True)
        else:
            message = "Wrong username or password"

    return render_template('login.html', message=message)

@app.route('/upload/<int:user_id>', methods=['GET', 'POST'])
def upload(user_id):
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        files = request.files.getlist('file')

        q = """
        select id+1 as 'next_id' from images
        order by id desc limit 1;
        """
        res = read_db(q)
        next_id = -1
        if len(res) > 0:
            next_id = res[0]['next_id']
        else:
            q = """
            truncate table images;
            """
            write_db(q)
            next_id = 1

        filenames = []
        file_ids = []

        for file in files:
            if file and allowed_file(file.filename):
                filename = str(next_id) + '_' + file.filename
                filenames.append(filename)
                file_ids.append(next_id)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                next_id += 1

        classifications = request.form.get('classifications').replace(' ', '')

        q = f"""
        insert into images (classifications, name)
        values {','.join([f"('{classifications}', '{filename}')" for filename in filenames])};
        """
        write_db(q)

        q = 'select user_id from users;'
        res = read_db(q)
        ids = [i['user_id'] for i in res]

        q = """
            insert into image_availability
            values 
        """
        q_extra = []
        for file_id in file_ids:
            q_extra.append(','.join([f"({file_id}, {id})" for id in ids]))
        q += ','.join(q_extra)
        print(q, flush=True)
        write_db(q)


    return render_template('upload.html')

if __name__ == "__main__":
    app.run(host=_HOST, port=_PORT)