import re, random, configparser, os
import sqlalchemy as sq
from telebot import TeleBot, types, custom_filters
from telebot.storage import StateMemoryStorage
from sqlalchemy.orm import sessionmaker

from models import create_tables, User, Word, Translation

config = configparser.ConfigParser()
config.read(f'{os.getcwd()}/settings.ini')

DSN = config['database']['dsn'] # DSN из конфига
engine = sq.create_engine(DSN)
Session = sessionmaker(bind=engine)
session = Session()

create_tables(engine)

TOKEN = config['bot']['token'] # Токен из конфига

state_storage = StateMemoryStorage()
bot = TeleBot(token=TOKEN, state_storage=state_storage)

class Commands:
    QUIZ = '\U00002B50 Начать квиз \U00002B50'
    SHOW_WORDS = 'Мои слова \U00002728'
    ADD_WORD = 'Добавить слово \U00002795'
    DELETE_WORD = 'Удалить слово \U00002796'

# Я пытался реализовать хранение через состояния бота, но так и не смог разобраться
# почему в функции проверки слова из контекстного менеджера достается не верное слово для проверки, хотя 
# если ответ верный я очищал состояние через delete_state и прошлое слово должно было удаляться

quiz_storage = {} # Словарь как локальное хранилище данных для квиза (самое по моему мнению удобное решение)
    
# Начальное меню
def main_menu(message):
    main_markup = types.ReplyKeyboardMarkup(row_width=2)
    buttons = [Commands.QUIZ, Commands.SHOW_WORDS, Commands.ADD_WORD, Commands.DELETE_WORD]
    main_markup.add(*buttons)
    greeting = 'Выбери команду из списка \U0001F52E'
    bot.send_message(message.chat.id, greeting, reply_markup=main_markup)

# Кнопка отмены
def cancel(message):
    msg = bot.send_message(message.chat.id, 'Возвращаемся к истокам...\U000023F3')
    main_menu(message)

def check_word(message):
    """Функция проверки пользовательского ввода на текст и соответствие шаблону"""
    if message.content_type != 'text': # Проверяем что сообщение является текстом
        return True
    word = message.text
    # Проверка, что введенное слово состоит из букв и не является эмодзи
    if not re.match(r'^[\w\s]+$', word):
        return True
    
    return False

def generate_words(message, type):
    """Функция генерации слов в зависимости от типа квиза"""
    user = session.query(User).filter_by(chat_id=message.chat.id).first()

    target_word = session.query(Word).filter_by(user_id=user.id).order_by(sq.func.random()).first() # Запрос рандомного слова
    target_translations = [data.translation for data in session.query(Translation)
                          .filter_by(word_id=target_word.id)] # Список всех переводов слова
    random.shuffle(target_translations)
    target_translation = target_translations[0] # Забираем только один перевод
    if type == 'ans' or type == 'no_ans':
        words = [word.word for word in session.query(Word)
                 .filter_by(user_id=user.id)
                 .filter(Word.word != target_word.word)
                 .order_by(sq.func.random())
                 .limit(3)] # Список 3 случайных слов
        words.append(target_word.word)
    else:
        print('Непредвиденная ошибка генерации слов для квиза.')
        return

    random.shuffle(words)
    target_word = target_word.word
    quiz_storage['target_word'] = target_word
    quiz_storage['target_translation'] = target_translation
    quiz_storage['words'] = words
    

# Обработка команды /start
@bot.message_handler(commands=['start'])
def start(message):
    """Начальное меню пользователя"""
    cid = message.chat.id
    uid = message.from_user.id
    
    user = session.query(User).filter_by(chat_id=cid).first()
    # session.delete(user)
    # session.commit()
    if not user:
        user = User(chat_id=cid, user_id=uid)
        session.add(user)
        session.commit()
        print(f'Пользователь с chat_id {message.chat.id} добавлен в базу данных')
        words = ["Apple", "Home", "Luck", "Honor", "Train", "Fish", "Star", "Wind", "Wall"]
        translations = ["Яблоко", "Дом", "Удача", "Честь", "Поезд", "Рыба", "Звезда", "Ветер", "Стена"]
        for word, translation in zip(words, translations):
            add_word = Word(word=word, user=user)
            add_translation = Translation(translation=translation, word=add_word)
            session.add_all([add_word, add_translation])
            session.commit()
    else:
        main_menu(message)
        print(f'Пользователь с chat_id {cid} уже существует в базе данных')
        return

    bot.send_message(message.chat.id, f'Привет, я учебный бот!\U0001F601')
    main_menu(message)

    

# Функции добавления слова в базу данных
@bot.message_handler(func=lambda message: message.text == Commands.ADD_WORD)
def add_word(message):
    """Команда ADD WORD"""
    add_word_markup = types.ReplyKeyboardMarkup(row_width=1)
    add_word_markup.add('Отмена')
    msg = bot.send_message(message.chat.id, 'Напиши слово, которое ты хочешь добавить \U00002600', reply_markup=add_word_markup)
    bot.register_next_step_handler(msg, process_add_word)

def process_add_word(message):
    """Процесс обработки введенного слова"""
    if check_word(message): # Проверка пользовательского ввода
        bot.send_message(message.chat.id, "Немного тебя не понял \U0001F625 Может попробуешь еще разок? \U0001F64F")
        add_word(message)  # Запрашиваем ввод снова
        return
    
    word = message.text
    if word.lower() == 'отмена':
        cancel(message)
        return
    
    user = session.query(User).filter_by(chat_id=message.chat.id).first()  # Находим пользователя по chat_id
    query = session.query(Word).filter_by(word=word, user_id=user.id).first() # Поиск слова на наличие в БД
    if query:
       msg = bot.send_message(message.chat.id, f'Вижу ты уже изучаешь слово "{word}" \U0001F63A Введи дополнительный перевод этого слова \U0001F43E')
    else:
        msg = bot.send_message(message.chat.id, f'Отлично! \U0001F63B Ты ввел слово "{word}", теперь введи его перевод)')
    bot.register_next_step_handler(msg, lambda msg: process_add_word_translate(msg, word))

def process_add_word_translate(message, word):
    """Процесс добавления слова и перевода в БД"""
    if check_word(message): # Проверка пользовательского ввода
        bot.send_message(message.chat.id, "Немного тебя не понял \U0001F625 Может попробуешь еще разок? \U0001F64F")
        add_word(message)  # Запрашиваем ввод снова
        return
    
    translation_text = message.text
    if translation_text.lower() == 'отмена':
        cancel(message)
        return
    word_text = word # Это что бы не было путаницы
    cid = message.chat.id
    user = session.query(User).filter_by(chat_id=cid).first()  # Находим пользователя по chat_id
    
    query_word = session.query(Word).filter_by(word=word_text, user_id=user.id).first() # Поиск слова на наличие в БД
    if not query_word:
        word = Word(word=word_text, user=user)  # Создаем запись слова, связывая его с пользователем
        translation = Translation(translation=translation_text, word=word)  # Создаем запись перевода
        
        session.add_all([word, translation])  # Добавляем записи в сессию
        bot.send_message(message.chat.id, "Слово успешно добавлено в твой список изучаемых слов \U0001F973")
    else:
        translation_query = session.query(Translation).filter_by(translation=translation_text, word_id=query_word.id).first()
        if translation_query: # Проверка на уникальность перевода для конкретного слова
            bot.send_message(message.chat.id, f'Ты уже вводил такой перевод слова "{word_text}" \U0001F914')
            add_word(message)
            return
        
        translation = Translation(translation=translation_text, word=query_word)
        session.add(translation)
        bot.send_message(message.chat.id, f'Еще один перевод слова "{word_text}" успешно сохранен \U0001F973')
    session.commit()  # Сохраняем изменения в базе данных

    main_menu(message)
    return


# Функции удаления слова из базы данных
@bot.message_handler(func=lambda message: message.text == Commands.DELETE_WORD)
def remove_word(message):
    """Формирование списка слов для удаления"""
    delete_markup = types.ReplyKeyboardMarkup(row_width=1)
    words = []
    func_but = 'Отмена'
    user = session.query(User).filter_by(chat_id=message.chat.id).first()
    for data in session.query(Word).filter_by(user_id=user.id):
        words.append(data.word)
    if words:
        words.append(func_but)
        delete_markup.add(*words)
        msg = bot.send_message(message.chat.id, 'Выбери слово из списка \U0001F480', reply_markup=delete_markup)
        bot.register_next_step_handler(msg, lambda msg: check(msg, words))
    else:
        bot.send_message(message.chat.id, 'Пока что удалять нечего, самое время начать изучать новые слова! \U0001F929')
        main_menu(message)
        return

def check(message, words):
    """Проверка подтвержения удаления выбранного слова"""
    word = message.text
    if word in words:
        if word.lower() == 'отмена':
            cancel(message)
            return
        check_markup = types.ReplyKeyboardMarkup(row_width=2)
        buttons = ['Да', 'Нет']
        check_markup.add(*buttons)
        msg = bot.send_message(message.chat.id, f'Подтверди удаление слова "{word}" \U0001F4A3', reply_markup=check_markup)
        bot.register_next_step_handler(msg, lambda msg: process_remove_word(msg, word))
    else:
        bot.send_message(message.chat.id, f'Что-то я не найду слово "{word}" в твоем списке \U0001F928', reply_markup=types.ReplyKeyboardRemove())
        remove_word(message)  # Снова вызываем функцию remove_word
        return
    
def process_remove_word(message, word):
    """Процесс удаления слова из БД"""
    if check_word(message):
        bot.send_message(message.chat.id, 'Не понял твой ответ \U0001F63F')
        remove_word(message)
        return
    elif message.text.lower() == 'нет':
        bot.send_message(message.chat.id, f'Отмена удаления слова "{word}"')
        main_menu(message)
        return
    elif message.text.lower() == 'да':
        user = session.query(User).filter_by(chat_id=message.chat.id).first()
        query = session.query(Word).filter_by(word=word, user_id=user.id).first()
        session.delete(query)
        session.commit()
        bot.send_message(message.chat.id, f'Слово "{word}" удалено из списка изучаемых слов \U0001F4A5')
        main_menu(message)
        return
    else:
        bot.send_message(message.chat.id, 'Не понял твой ответ \U0001F63F')
        remove_word(message)
        return
    
# Функция выведения списка изучаемых слов
@bot.message_handler(func=lambda message: message.text == Commands.SHOW_WORDS)
def show_words(message):
    words = {} # слово: [переводы слова]
    user = session.query(User).filter_by(chat_id=message.chat.id).first()
    words_query = session.query(Word).filter_by(user_id=user.id)
    for word in words_query:
        for translation in session.query(Translation).filter_by(word_id=word.id):
            if word.word in words:
                words[word.word].append(translation.translation)
            else:
                words[word.word] = [translation.translation]
    if words:
        words_list = []
        for key, value in words.items():
            words_list.append(f'{key} ({", ".join(value)})')
        words_text = "\n".join(words_list)
        bot.send_message(message.chat.id, f'Слов на изучении: {len(words)} \U0001F92F\nСлова которые ты изучаешь \U0001F929\n{words_text}')
        main_menu(message)
        return
    else:
        bot.send_message(message.chat.id, 'Пока что здесь пусто...\U0001F4A4')
        main_menu(message)
        return

# Функции прохождения квиза
@bot.message_handler(func=lambda message: message.text == Commands.QUIZ)
def quiz(message):
    """Функция прохождения квиза"""
    quiz_type_markup = types.ReplyKeyboardMarkup(row_width=2)
    buttons = ['С вариантами ответов', 'Без вариантов ответа', 'Отмена']
    quiz_type_markup.add(*buttons)

    bot_message = bot.send_message(message.chat.id, 'Выбери способ прохождения квиза:', reply_markup=quiz_type_markup)
    bot.register_next_step_handler(message, check_quiz_type)

def check_quiz_type(message):
    """Функция проверки ответа"""
    answer = message.text
    if check_word(message):
        bot.send_message(message.chat.id, 'Не совсем понял что ты хотел мне сказать \U0001F914 Попробуем еще разок \U0001F44C')
        quiz(message)
        return
    elif answer.lower() == 'с вариантами ответов':
        start_quiz(message, 'ans')
        return
    elif answer.lower() == 'без вариантов ответа':
        start_quiz(message, 'no_ans')
        return
    elif answer.lower() == 'отмена':
        cancel(message)
        return
    else:
        bot.send_message(message.chat.id, 'Не совсем понял что ты хотел мне сказать \U0001F914 Попробуем еще разок \U0001F44C')
        quiz(message)
        return

def start_quiz(message, type):
    """Функция прохождения квизов"""
    user = session.query(User).filter_by(chat_id=message.chat.id).first()
    
    if quiz_storage: # Если словарь со словами не пуст
        target_word = quiz_storage['target_word']
        target_translation = quiz_storage['target_translation']
        words = quiz_storage['words']
        random.shuffle(words)
    else: # Если словарь пустой
        generate_words(message, type) # Генерируем слова для квиза
        target_word = quiz_storage['target_word']
        target_translation = quiz_storage['target_translation']
        words = quiz_storage['words']

    cancel_but = "Закончить квиз"
    if type == 'ans':
        quiz_markup = types.ReplyKeyboardMarkup(row_width=2)
        quiz_markup.add(*words, cancel_but)
        msg = bot.send_message(message.chat.id, f'Выбери перевод слова:\n\U0001F1F7\U0001F1FA {target_translation} \U0001F440', reply_markup=quiz_markup)
    else:
        quiz_markup = types.ReplyKeyboardMarkup(row_width=1)
        quiz_markup.add(cancel_but)
        msg = bot.send_message(message.chat.id, f'Введи перевод слова:\n\U0001F1F7\U0001F1FA {target_translation} \U0001F440')
        bot.send_message(message.chat.id, 'Закончить квиз: /stop', reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, lambda msg: check_answers(msg, type))

def check_answers(message, type):
    """Функция проверки ответа"""
    target_word = quiz_storage['target_word']
    
    if message.text and message.text.lower() == 'закончить квиз' or message.text == '/stop':
        quiz_storage.clear() # Очищаем словарь со словами
        quiz(message)
        return
    elif check_word(message): # Проверим слово на соответствие шаблону
        bot.send_message(message.chat.id, 'Ты прислал мне совсем что-то другое \U0001F92F\nДавай попробуем еще разок \U0001F609')
        start_quiz(message, type)
        return
    elif message.text.lower() == target_word.lower():
        bot.send_message(message.chat.id, 'Поздравляю! \U0001F973 Это верный ответ!')
        quiz_storage.clear() # Очищаем словарь со словами
        start_quiz(message, type)
        return
    elif message.text.lower() != target_word.lower():
        bot.send_message(message.chat.id, 'К сожалению это не верный ответ... \U0001F622 Попробуй еще разок \U0001F91E')
        start_quiz(message, type)
        return

session.close()

if __name__ == '__main__':
    print('Bot is running')
    bot.add_custom_filter(custom_filters.StateFilter(bot))
    bot.infinity_polling(skip_pending=True)
