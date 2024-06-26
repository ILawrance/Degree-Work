from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from config import (DB_HOST, DB_NAME, DB_USER, DB_PASS,
                    DB_CLOUD_user, DB_CLOUD_password, DB_CLOUD_host, DB_CLOUD_port, DB_CLOUD_dbname)

# Определяем базовый класс
Base = declarative_base()

# Создаем движок и сессию
#DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
DATABASE_URL = (f"postgresql+psycopg2:"
                f"//{DB_CLOUD_user}:{DB_CLOUD_password}@{DB_CLOUD_host}:{DB_CLOUD_port}/{DB_CLOUD_dbname}")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)




# Определяем модели
class Group(Base):
    __tablename__ = 'Groups'
    group_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    date_start = Column(Date, nullable=False)
    date_end = Column(Date, nullable=False)
    student = relationship("Student", back_populates="group")


class Student(Base):
    __tablename__ = 'Students'
    student_id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(255), nullable=False)
    second_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password = Column(String(512), nullable=False)
    group_id = Column(Integer, ForeignKey('Groups.group_id'))
    group = relationship("Group", back_populates="student")
    student_lesson = relationship("StudentLesson", back_populates="student")
    test = relationship("Test", back_populates="student")


class Teacher(Base):
    __tablename__ = 'Teachers'
    teacher_id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(255), nullable=False)
    second_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password = Column(String(512), nullable=False)
    lesson = relationship("Lesson", back_populates="teacher")
    option_key = relationship("OptionKey", back_populates="teacher")
    option_value = relationship("OptionValue", back_populates="teacher")


class Test(Base):
    __tablename__ = 'Tests'
    test_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    test_type = Column(String(255), nullable=False)
    score = Column(String(255), nullable=False)
    datetime = Column(DateTime, nullable=False)
    student_id = Column(Integer, ForeignKey("Students.student_id"), nullable=False)
    student = relationship("Student", back_populates="test")
    test_quest = relationship("TestQuest", back_populates="test")


class Quest(Base):
    __tablename__ = 'Quests'
    quest_id = Column(Integer, primary_key=True, autoincrement=True)
    issue = Column(Text)
    options = Column(Text)
    test_quest = relationship("TestQuest", back_populates="quest")
    quest_option_value = relationship("QuestOptionValue", back_populates="quest")
    quest_option_key = relationship("QuestOptionKey", back_populates="quest")


class TestQuest(Base):
    __tablename__ = 'Tests_Quests'
    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(Integer, ForeignKey("Tests.test_id"), nullable=False)
    quest_id = Column(Integer, ForeignKey("Quests.quest_id"), nullable=False)
    test = relationship("Test", back_populates="test_quest")
    quest = relationship("Quest", back_populates="test_quest")


class StudentLesson(Base):
    __tablename__ = 'Students_lessons'
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('Students.student_id'), nullable=False)
    lesson_id = Column(Integer, ForeignKey('Lessons.lesson_id'), nullable=False)
    student = relationship("Student", back_populates='student_lesson')
    lesson = relationship("Lesson", back_populates='student_lesson')


class Lesson(Base):
    __tablename__ = 'Lessons'
    lesson_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    text_material = Column(Text)
    video_material = Column(String(512))
    teacher_id = Column(Integer, ForeignKey('Teachers.teacher_id'), nullable=False)
    teacher = relationship("Teacher", back_populates="lesson")
    student_lesson = relationship("StudentLesson", back_populates="lesson")


class QuestOptionKey(Base):
    __tablename__ = 'Quests_options_keys'
    id = Column(Integer, primary_key=True, autoincrement=True)
    quest_id = Column(Integer, ForeignKey('Quests.quest_id'))
    option_key_id = Column(Integer, ForeignKey('Options_keys.option_key_id'))
    quest = relationship("Quest", back_populates="quest_option_key")
    option_key = relationship("OptionKey", back_populates="quest_option_key")

class QuestOptionValue(Base):
    __tablename__ = 'Quests_options_values'
    id = Column(Integer, primary_key=True, autoincrement=True)
    quest_id = Column(Integer, ForeignKey('Quests.quest_id'))
    option_value_id = Column(Integer, ForeignKey('Options_values.option_value_id'))
    quest = relationship("Quest", back_populates="quest_option_value")
    option_value = relationship("OptionValue", back_populates="quest_option_value")


class OptionKey(Base):
    __tablename__ = 'Options_keys'
    option_key_id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(String(512), nullable=False)
    teacher_id = Column(Integer, ForeignKey('Teachers.teacher_id'), nullable=False)
    teacher = relationship("Teacher", back_populates="option_key")
    quest_option_key = relationship("QuestOptionKey", back_populates="option_key")


class OptionValue(Base):
    __tablename__ = 'Options_values'
    option_value_id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(String(512), nullable=False)
    teacher_id = Column(Integer, ForeignKey('Teachers.teacher_id'), nullable=False)
    option_key_id = Column(Integer, ForeignKey('Options_keys.option_key_id'), nullable=True)
    teacher = relationship("Teacher", back_populates="option_value")
    option_key = relationship("OptionKey", foreign_keys=[option_key_id])
    quest_option_value = relationship("QuestOptionValue", back_populates="option_value")


Base.metadata.create_all(bind=engine)
