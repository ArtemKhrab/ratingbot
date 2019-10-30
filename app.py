from flask import Flask
from config import token, key, conn, cursor
import telebot
import requests


app = Flask(__name__)
bot = telebot.TeleBot(token)


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.from_user.id, 'Привет, я тебе помогу следить за твоими оценками. '
                                           'Для авторизации используйте /auth. '
                                           'Чтобы выйти на любом этапе - используй q. '
                                           'Если ты уже логинился, можешь сразу смотреть рейтинг /show')


@bot.message_handler(commands=['auth'])
def auth(message):
    cursor.execute('SELECT * FROM student where telegram_id = %(telegram_id)s',
                   {'telegram_id': str(message.chat.id)})
    records = cursor.fetchall()
    if records == []:
        bot.send_message(message.from_user.id, 'Введите свой номер телефона !не в меджународном формате!')
        bot.register_next_step_handler(message, get_telephone)
    else:
        bot.send_message(message.from_user.id, 'Вы уже зарегистрированны!')
        return


def get_telephone(message):
    if message.text == 'q':
        return
    try:
        int(message.text)
    except ValueError:
        bot.send_message(message.from_user.id, 'Введите, пожалуйста, номер без символов')
        bot.register_next_step_handler(message, get_telephone)
        return
    generate_code(message)


def generate_code(message):
    telephone = message.text
    try:
        response = requests.post(f'http://apis.kpi.ua/api/identities/secret/?phone={telephone}',
                    headers={'Authorization': key})
    except requests.ConnectionError:
        bot.send_message(message.chat.id, 'В данный момент сервер не отвечает(')
        return
    print(f'generate code: {response.status_code}')
    if response.status_code == 200:
        bot.send_message(message.from_user.id, 'Хорошо, теперь введите код')
        bot.register_next_step_handler(message, identities, telephone)
    elif response.status_code == 404 or response.status_code == 400:
        bot.send_message(message.from_user.id, 'Неправильно введен номер, либо не сущевствует в базе.\nВведите еще раз')
        bot.register_next_step_handler(message, get_telephone)
        return


def identities(message, telephone):
    if message.text == 'q':
        return
    try:
        int(message.text)
    except ValueError:
        bot.send_message(message.from_user.id, 'Введите код')
        bot.register_next_step_handler(message, identities, telephone)
        return
    try:
        response = requests.get(f'http://apis.kpi.ua/api/identities/?phone={telephone}&secret={message.text}',
                    headers={'Authorization': key})
    except requests.ConnectionError:
        bot.send_message(message.chat.id, 'В данный момент сервер не отвечает(')
        return
    print(f'identities: {response.status_code}')
    if response.status_code == 200:
        student_id = response.json()['personId']
        cursor.execute('INSERT INTO student (telegram_id, api_id) VALUES (%(telegram_id)s, %(api_id)s)',
                       {'telegram_id': str(message.chat.id), 'api_id':  student_id})
        conn.commit()
        bot.send_message(message.chat.id, 'Теперь можете посмотреть свои двойки, введите /show')
    else:
        bot.send_message(message.from_user.id, 'Некорректно введен код')
        bot.register_next_step_handler(message, identities, telephone)
        return

@bot.message_handler(commands=['show'])
def get_rating(message):
    cursor.execute('SELECT api_id FROM student WHERE telegram_id = %(telegram_id)s',
                   {'telegram_id': str(message.chat.id)})
    student_id = cursor.fetchone()
    if student_id is None:
        bot.send_message(message.chat.id, 'Сначала залогинтесь')
        return
    else:

        semester = get_current_semester(message, student_id[0])
        bot.send_message(message.chat.id, f'Вы сейчас учитесь на {semester} семестре')
        message.text = int(semester)-1
        get_rating_loop(message, student_id[0], semester)


def get_rating_loop(message, student_id, semester):
    if message.text == 'q':
        return
    try:
        semester_id = int(message.text)
        max_semester = int(semester)
    except ValueError:
        bot.send_message(message.from_user.id, 'Номер семестра не может содержать букв, введите заново')
        bot.register_next_step_handler(message, get_rating_loop, student_id, semester)
        return
    if semester_id > max_semester:
        bot.send_message(message.from_user.id, 'Семестр не может быть больше текущего\nВведите еще раз')
        bot.register_next_step_handler(message, get_rating_loop, student_id, max_semester)
    elif semester_id <= 0:
        bot.send_message(message.from_user.id, 'Семестр не может быть меньше, или ровнятся нулю\nВведите еще раз')
        bot.register_next_step_handler(message, get_rating_loop, student_id, max_semester)
    else:
        try:
            response = requests.get(f'http://apis.kpi.ua/api/marks?studentId={student_id}&semesterId={semester_id}',
                        headers={'Authorization': key})
        except Exception:
            bot.send_message(message.chat.id, 'В данный момент сервер не отвечает(')
            return
        print(f'get rating loop: {response.status_code}')
        if response.status_code != 200:
            bot.send_message(message.from_user.id, 'Что-то пошло не так, попробуйте чуть позже')
            return
        else:
            full_response = ''
            for disciplines in response.json():
                full_response += f'{disciplines["disciplineName"]}, {disciplines["studyTypeName"]}: {disciplines["mark"]}\n'
            bot.send_message(message.from_user.id, full_response)
            bot.send_message(message.from_user.id, f'Если хотите посмотреть предыдущие, введите номер семестра\nВы сейчас просматриваете {message.text}-й семестр')
            bot.register_next_step_handler(message, get_rating_loop, student_id, max_semester)


def get_current_semester(message, student_id):
    try:
        response = requests.get(f'http://apis.kpi.ua/api/information/current-semester/?studentId={student_id}',
                    headers={'Authorization': key})
    except requests.ConnectionError:
        bot.send_message(message.chat.id, 'В данный момент сервер не отвечает(')
        return
    print(f'get current semester: {response.status_code}')
    return response.json()['currentSemester']


bot.polling()
if __name__ == '__main__':
    app.run()
