from flask import Flask
from config import token, key
import telebot
import requests

app = Flask(__name__)
bot = telebot.TeleBot(token)


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.from_user.id, 'Привет:)')
    bot.send_message(message.from_user.id, 'Для авторизации используйте /auth')


@bot.message_handler(commands=['auth'])
def auth(message):
    bot.send_message(message.from_user.id, 'Введите свой номер телефона !не в меджународном формате!')
    bot.register_next_step_handler(message, get_telephone)


def get_telephone(message):
    try:
        int(message.text)
    except ValueError:
        bot.send_message(message.from_user.id, 'Введите, пожалуйста, номер без символов')
        bot.register_next_step_handler(message, get_telephone)
        return
    generate_code(message)


def generate_code(message):
    telephone = message.text
    response = requests.post(f'http://apis.kpi.ua/api/identities/secret/?phone={telephone}',
                 headers={'Authorization': key})
    if response.status_code == 200:
        bot.send_message(message.from_user.id, 'Хорошо, теперь введите код')
        bot.register_next_step_handler(message, identities, telephone)
    elif response.status_code == 404 or response.status_code == 400:
        bot.send_message(message.from_user.id, 'Неправильно введен номер, либо не сущевствует в базе.\nВведите еще раз')
        bot.register_next_step_handler(message, get_telephone)
        return


def identities(message, telephone):
    try:
        int(message.text)
    except ValueError:
        bot.send_message(message.from_user.id, 'Введите код')
        bot.register_next_step_handler(message, identities, telephone)
        return
    response = requests.get(f'http://apis.kpi.ua/api/identities/?phone={telephone}&secret={message.text}',
                 headers={'Authorization': key})
    if response.status_code == 200:
        student_id = response.json()['personId']
        get_rating(message, student_id)
    else:
        bot.send_message(message.from_user.id, 'Некорректно введен код')
        bot.register_next_step_handler(message, identities, telephone)
        return


def get_rating(message, student_id):
    semester = get_current_semester(student_id)
    message.text = int(semester)-1
    get_rating_loop(message, student_id, semester)


def get_rating_loop(message, student_id, semester):
    try:
        semester_id = int(message.text)
        max_semester = int(semester)
    except ValueError:
        bot.send_message(message.from_user.id, 'Номер семестра не может содержать букв, введите заново')
        bot.register_next_step_handler(message, get_rating_loop, student_id, semester)
        return
    if (semester_id <= max_semester) and (semester_id > 0):
        response = requests.get(f'http://apis.kpi.ua/api/marks?studentId={student_id}&semesterId={semester_id}',
                     headers={'Authorization': key})
        if response.status_code != 200:
            bot.send_message(message.from_user.id, 'Походу код аутентификации сдох, перезалогинтесь /auth')
            return
        else:
            full_response = ''
            for disciplines in response.json():
                full_response += f'{disciplines["disciplineName"]}, {disciplines["studyTypeName"]}: {disciplines["mark"]}\n'
            bot.send_message(message.from_user.id, full_response)
            bot.send_message(message.from_user.id, f'Если хотите посмотреть предыдущие, введите номер семестра\nВы сейчас на {max_semester}')
            bot.register_next_step_handler(message, get_rating_loop, student_id, max_semester)
    else:
        bot.send_message(message.from_user.id, 'Семестр не может быть больше текущего, либо меньше 0\nВведите еще раз')
        bot.register_next_step_handler(message, get_rating_loop, student_id, max_semester)


def get_current_semester(student_id):
    response = requests.get(f'http://apis.kpi.ua/api/information/current-semester/?studentId={student_id}',
                 headers={'Authorization': key})
    return response.json()['currentSemester']


bot.polling()
if __name__ == '__main__':
   app.run()
