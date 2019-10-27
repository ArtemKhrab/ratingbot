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
def show_rating(message):
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
        bot.send_message(message.from_user.id, student_id)
    else:
        bot.send_message(message.from_user.id, 'Некорректно введен код')
        bot.send_message(message.from_user.id, response.text)
        bot.register_next_step_handler(message, identities, telephone)
        return


bot.polling()
if __name__ == '__main__':
    app.run()

