import sqlalchemy as sq
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    """Таблица диалогов с пользователями"""
    __tablename__ = 'users'

    id = sq.Column(sq.Integer, primary_key=True)
    chat_id = sq.Column(sq.BigInteger, nullable=False, unique=True)
    user_id = sq.Column(sq.BigInteger, nullable=False, unique=True)

    words = relationship('Word', back_populates='user', cascade="all, delete-orphan")

class Word(Base):
    """Таблица английских слов"""
    __tablename__ = 'words'

    id = sq.Column(sq.Integer, primary_key=True)
    user_id = sq.Column(sq.Integer, sq.ForeignKey('users.id'), nullable=False)  # Изменено chat_id на user_id
    word = sq.Column(sq.String(length=48), nullable=False)

    user = relationship('User', back_populates='words')
    translations = relationship('Translation', back_populates='word', cascade="all, delete-orphan")  # Исправлено имя поля translations

class Translation(Base):
    """Таблица переводов слов"""
    __tablename__ = 'translations'  # Изменено имя таблицы на множественное число

    id = sq.Column(sq.Integer, primary_key=True)
    word_id = sq.Column(sq.Integer, sq.ForeignKey('words.id'), nullable=False)
    translation = sq.Column(sq.String(length=48), nullable=False)

    word = relationship('Word', back_populates='translations')  # Исправлено имя поля translations

def create_tables(engine):
    #Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
