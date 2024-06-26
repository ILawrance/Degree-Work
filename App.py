from datetime import datetime
import random

import langchain.schema
from langchain.schema import HumanMessage
from langchain_community.chat_models.gigachat import GigaChat
from st_aggrid import AgGrid, GridOptionsBuilder
from streamlit_option_menu import option_menu
import pandas as pd
import streamlit as st
import boto3, bcrypt, uuid, requests
from PIL import Image
from io import BytesIO
from botocore.client import Config
from sqlalchemy import create_engine, text, func, Integer, cast, and_, distinct
from sqlalchemy.orm import sessionmaker
from streamlit_quill import st_quill
from models import (Base, Student, Group, Teacher, StudentLesson, Lesson, Test, TestQuest, Quest, OptionKey,
                    OptionValue)
# from config import (path_to_folder, YANDEX_CLOUD_KEY_ID,
#                   YANDEX_CLOUD_SECRET_KEY, YANDEX_BUCKET_NAME, END_POINT_URL, AUTH_DATA_GIGACHAT, DB_CLOUD_user,
#                   DB_CLOUD_password, DB_CLOUD_host,DB_CLOUD_port, DB_CLOUD_dbname)

YANDEX_BUCKET_NAME = st.secrets['YANDEX_BUCKET_NAME']
END_POINT_URL = st.secrets['END_POINT_URL']


DATABASE_URL = (f"postgresql+psycopg2:"
                f"//{st.secrets['DB_CLOUD_user']}:{st.secrets['DB_CLOUD_password']}@{st.secrets['DB_CLOUD_host']}:{st.secrets['DB_CLOUD_port']}/{st.secrets['DB_CLOUD_dbname']}")
engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=30)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

SALT = b'$2b$12$K1Q8Jf5U6s9bJ8qE6dEVOe'

s3 = boto3.client(
    's3',
    endpoint_url=st.secrets['END_POINT_URL'],
    aws_access_key_id=st.secrets['YANDEX_CLOUD_KEY_ID'],
    aws_secret_access_key=st.secrets['YANDEX_CLOUD_SECRET_KEY'],
    config=Config(signature_version='s3v4'),
    region_name='ru-central1'  # Регион Yandex Cloud
)


auth = st.secrets['AUTH_DATA_GIGACHAT']


# Функция для получения сессии
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if "responses" not in st.session_state:
    st.session_state.responses = {}
if "is_started" not in st.session_state:
    st.session_state.is_started = False
if "starting" not in st.session_state:
    st.session_state.starting = False
if "blocks" not in st.session_state:
    st.session_state.blocks = []
if 'editor_content' not in st.session_state:
    st.session_state.editor_content = ""

def fetch_image_from_url(image_url):
    try:
        response = requests.get(image_url)
        response.raise_for_status()  # Проверка на успешный ответ
        image = Image.open(BytesIO(response.content))
        return image
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при загрузке изображения: {e}")
        return None


def check_contains_content(list_for_check, content):
    for item in list_for_check:
        if item.content == content:
            return True
    return False


def parse_key(key):
    try:
        key_part = key.split('_opt=')[0].split('key=')[1]
        val_part = key.split('_opt=')[1]
        return key_part, val_part
    except IndexError:
        return None, None


def generate_question_image_submit():
    if 'responses' not in st.session_state:
        st.session_state.responses = {}
    if 'questions' not in st.session_state:
        st.session_state.questions = []

    if not st.session_state.questions:
        for i in range(5):
            db = next(get_db())
            images = db.query(OptionKey).all()
            values = db.query(OptionValue).filter(OptionValue.option_key_id.isnot(None)).all()
            question = {"id": i, "type": "image" if random.randint(1, 100) > 50 else "text"}
            if question["type"] == "image":
                random_values_and_one_correct = set()
                random_img = random.choice(images)
                correct_pair_value = db.query(OptionValue).filter_by(
                    option_key_id=random_img.option_key_id).first()
                random_values_and_one_correct.add(correct_pair_value.content)
                while len(random_values_and_one_correct) < 4:
                    random_value = random.choice(values)
                    random_values_and_one_correct.add(random_value.content)
                question["content"] = {
                    "image": random_img.content,
                    "options": list(random_values_and_one_correct)
                }
            else:
                random_img_and_one_correct = set()
                random_val = random.choice(values)
                correct_pair_img = db.query(OptionKey).filter_by(
                    option_key_id=random_val.option_key_id).first()
                random_img_and_one_correct.add(correct_pair_img.content)
                while len(random_img_and_one_correct) < 4:
                    random_img = random.choice(images)
                    random_img_and_one_correct.add(random_img.content)
                question["content"] = {
                    "text": random_val.content,
                    "options": list(random_img_and_one_correct)
                }
            st.session_state.questions.append(question)

    for question in st.session_state.questions:
        st.text(f"Вопрос №{question['id'] + 1}")
        if question["type"] == "image":
            col1, col2, col3 = st.columns([2, 1, 2])
            with col1:
                st.write("Дана диаграмма ДКА, на которой зеленым треугольником отмечено начальное состояние, \n"
                         "а красным шестиугольником отмечено(ы) заключительное(ые) состояние(я). \n"
                         "Выяснить какое слово будет допущено этим автоматом.")
                st.image(fetch_image_from_url(question["content"]["image"]), width=200, use_column_width=True)
            with col3:
                for option in question["content"]["options"]:
                    checkbox_key = f"q{question['id'] + 1}_key={option}_opt={question['content']['image']}"
                    st.session_state.responses[checkbox_key] = st.checkbox(f"{option}", key=checkbox_key)
        else:
            col1, col2, col3 = st.columns([2, 1, 2])
            with col1:
                st.text(
                    f"Дано слово {question['content']['text']}.\n"
                    f"Выяснить какой ДКА \nдопустит это слово. \n"
                    f"На диаграммах ДКА \nзелеными треугольниками \n"
                    f"отмечаются начальные состояния, \n"
                    f"красными шестиугольниками – \nзаключительные.")
            with col3:
                counter = 1
                for img in question["content"]["options"]:
                    col1b, col2b = st.columns([1, 7])
                    checkbox_key = f"q{question['id'] + 1}_key={question['content']['text']}_opt={img}"
                    with col1b:
                        st.session_state.responses[checkbox_key] = st.checkbox(f"{counter}", key=checkbox_key,
                                                                               label_visibility="hidden")
                    with col2b:
                        st.image(fetch_image_from_url(img), use_column_width=True)
                        if counter < 4:
                            st.write("<hr>", unsafe_allow_html=True)
                    counter += 1
        st.write("<hr>", unsafe_allow_html=True)

    col1a, col2a, col3a = st.columns(3)
    with col2a:
        if st.form_submit_button("Закончить тест"):
            st.session_state.is_started = True
            st.rerun()


def upload_image_to_yandex_cloud(image_data, image_name):
    unique_filename = str(uuid.uuid4()) + "_" + image_name
    path_to_file = f"{st.secrets['path_to_folder']}{unique_filename}"
    try:
        s3.put_object(Bucket=YANDEX_BUCKET_NAME, Key=path_to_file, Body=image_data)
        image_url = f"{END_POINT_URL}/{YANDEX_BUCKET_NAME}/{path_to_file}"
        return image_url
    except Exception as e:
        print(f"Ошибка при загрузке изображения: {e}")
        return None


def save_option_value(content, teacher_id, image_url=None):
    db = SessionLocal()
    try:
        new_option_value = OptionValue(content=content, teacher_id=teacher_id,
                                       option_key_id=get_image_id_by_url(image_url))
        db.add(new_option_value)
        db.commit()
        db.refresh(new_option_value)
        return new_option_value.option_value_id
    except Exception as e:
        st.error(f"Ошибка при добавлении записи в базу: {e}")
    finally:
        db.close()


def save_option_key_image(content, teacher_id):
    db = SessionLocal()
    try:
        new_option_key_image = OptionKey(content=content, teacher_id=teacher_id)
        db.add(new_option_key_image)
        db.commit()
        db.refresh(new_option_key_image)
        return new_option_key_image.option_key_id
    except Exception as e:
        st.error(f"Ошибка при добавлении записи в базу: {e}")
    finally:
        db.close()


def delete_option_value(id):
    db = next(get_db())
    try:
        # Находим запись по заданному id и удаляем её
        db.query(OptionValue).filter_by(option_value_id=id).delete()
        db.commit()
        return True  # Успешно удалено
    except Exception as e:
        db.rollback()
        print(f"Ошибка при удалении записи: {e}")
        return False  # Ошибка при удалении
    finally:
        db.close()


def delete_option_key_image(id):
    db = next(get_db())
    try:
        db.query(OptionKey).filter_by(option_key_id=id).delete()
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Ошибка при удалении записи: {e}")
        return False  # Ошибка при удалении
    finally:
        db.close()


# Функция для регистрации пользователя
def register_user(first_name, second_name, email, password, is_teacher):
    # Хеширование пароля
    hashed_password = hash_password(password)
    db = next(get_db())
    if is_teacher:
        new_user = Teacher(first_name=first_name, second_name=second_name,
                           email=email, password=hashed_password.decode('utf-8'))
    else:
        new_user = Student(first_name=first_name, second_name=second_name,
                           email=email, password=hashed_password.decode('utf-8'))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# Функция для авторизации пользователя
def authenticate_user(email, password, is_teacher):
    db = next(get_db())
    if is_teacher:
        user = db.query(Teacher).filter_by(email=email).first()
    else:
        user = db.query(Student).filter_by(email=email).first()

    if user and check_password(password, user.password.encode('utf-8')):
        return user
    else:
        return None


# Хеширование пароля с использованием соли
def hash_password(password):
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), SALT)
    return hashed_password


# Проверка пароля с использованием соли
def check_password(input_password, hashed_password):
    # Проверка пароля с использованием фиксированной соли
    return bcrypt.checkpw(input_password.encode('utf-8'), hashed_password)


def get_all_images():
    db = next(get_db())
    images = db.query(OptionKey).all()
    return images


def get_all_values_images():
    db = next(get_db())
    values_images = db.query(OptionValue).filter(OptionValue.option_key_id.isnot(None)).all()
    return values_images


def get_all_values_text():
    db = next(get_db())
    values_text = db.query(OptionValue).filter(OptionValue.option_key_text_id.isnot(None)).all()
    return values_text


# Функция для получения всех студентов
def get_all_students():
    db = next(get_db())
    students = db.query(Student).all()
    return students


# Отображение всех студентов таблицей
def students_table():
    st.header("Список всех студентов")
    students = get_all_students()
    if students:
        student_data = [{"ID": student.student_id, "Имя": student.first_name, "Фамилия": student.second_name,
                         "Email": student.email, "Группа": student.group_id} for student in students]
        st.table(student_data)
    else:
        st.write("Нет зарегистрированных студентов.")


def get_all_groups():
    db = next(get_db())
    groups = db.query(Group).all()
    return groups


def all_groups_table():
    st.header("Все группы")
    groups = get_all_groups()
    if groups:
        groups_data = [{"ID": group.group_id, "Название": group.name, "Дата начала": group.date_start,
                        "Дата окончания": group.date_end} for group in groups]
        st.table(groups_data)
    else:
        st.write("Групп пока не добавлено")


# Функция для обновления группы студента
def assign_group_to_student(student_id, group_id):
    db = next(get_db())
    student = db.query(Student).filter_by(student_id=student_id).first()
    if student:
        student.group_id = group_id
        db.commit()
        return True
    return False


def assign_data_to_student(student_id, first_name, second_name, email):
    db = next(get_db())
    student = db.query(Student).filter_by(student_id=student_id).first()
    if student:
        student.first_name = first_name
        student.second_name = second_name
        student.email = email
        db.commit()
        return True
    return False


def assign_data_to_teacher(teacher_id, first_name, second_name, email):
    db = next(get_db())
    teacher = db.query(Teacher).filter_by(teacher_id=teacher_id).first()
    if teacher:
        teacher.first_name = first_name
        teacher.second_name = second_name
        teacher.email = email
        db.commit()
        return True
    return False


def get_image_id_by_url(image_url):
    db = next(get_db())
    image = db.query(OptionKey).filter_by(content=image_url).first()
    db.close()
    if image:
        return image.option_key_id
    return None


def get_value_id_by_text(text):
    db = next(get_db())
    text = db.query(OptionValue).filter_by(content=text).first()
    db.close()
    if text:
        return text.option_value_id
    return None


def get_option_key_img_id_by_value_id(value_id):
    db = next(get_db())
    val = db.query(OptionValue).filter_by(option_value_id=value_id).first()
    db.close()
    if val:
        return val.option_key_id
    return None


# Функция для получения названия группы по её ID
def get_group_name_by_id(group_id):
    db = next(get_db())
    group = db.query(Group).filter_by(group_id=group_id).first()
    db.close()
    if group:
        return group.name
    return "Без группы"


# Функция для получения ID группы по её названию
def get_group_id_by_name(group_name):
    db = next(get_db())
    group = db.query(Group).filter_by(name=group_name).first()
    db.close()
    if group:
        return group.group_id
    return "Нет такой группы"


def get_questions_by_test_id(test_id):
    # Получить объекты Quest, связанные с заданным тестом
    db = next(get_db())
    test_quests = (
        db.query(Quest)
        .join(TestQuest, Quest.quest_id == TestQuest.quest_id)
        .filter(TestQuest.test_id == test_id)
        .all()
    )
    return test_quests


def generate_lecture_constructor():
    lecture_name = st.text_input("Введите название лекции")
    video_link = st.text_input("Вставьте ссылку на видео")
    st.write("Контент лекции:")
    editor_content = st_quill(key="quill", placeholder="Добавьте контент здесь...", html=True)
    if editor_content:
        st.session_state.editor_content = editor_content
    if st.button("Добавить лекцию"):
        if editor_content:
            db = next(get_db())
            new_lesson = Lesson(
                name=lecture_name,
                video_material=video_link,
                text_material=st.session_state.editor_content,
                teacher_id=user.teacher_id
            )
            db.add(new_lesson)
            db.commit()
            db.close()
            st.success("Лекция добавлена")



def show_registration_page():
    st.sidebar.radio("Навигация", ["Вход"])
    # Выбор между регистрацией и авторизацией
    auth_option = st.selectbox("Выберите опцию", ["Войти", "Зарегистрироваться"])
    if auth_option == "Зарегистрироваться":
        st.header("Зарегистрироваться")
        first_name = st.text_input("Имя")
        second_name = st.text_input("Фамилия")
        email = st.text_input("Email")
        password = st.text_input("Пароль", type="password")
        is_teacher = st.checkbox("Я преподаватель")
        if st.button("Зарегистрироваться"):
            if first_name and second_name and email and password:
                user = register_user(first_name, second_name, email, password, is_teacher)
                if user:
                    st.success("Регистрация прошла успешно!")
                else:
                    st.error("Ошибка при регистрации.")
            else:
                st.error("Пожалуйста, заполните все поля.")

    elif auth_option == "Войти":
        st.header("Войти")
        email = st.text_input("Email")
        password = st.text_input("Пароль", type="password")
        is_teacher = st.checkbox("Я преподаватель")
        if st.button("Войти"):
            if email and password:
                user = authenticate_user(email, password, is_teacher)
                if user:
                    st.session_state['user'] = user
                    st.session_state['is_teacher'] = is_teacher
                    st.success("Авторизация прошла успешно!")
                    st.rerun()  # Перезапуск скрипта после успешной авторизации
                else:
                    st.error("Неверные учетные данные.")
            else:
                st.error("Пожалуйста, заполните все поля.")
    st.info("Пожалуйста, авторизуйтесь или зарегистрируйтесь.")


# Страница лекций ученика
def show_lecture_page_stud():
    st.markdown(
        """
        <style>
        .title {
            text-align: center;
        }
        </style>
        <h1 class="title">Лекции</h1>
        """,
        unsafe_allow_html=True
    )
    st.header("Просмотр лекций")
    db = next(get_db())
    lectures = db.query(Lesson).all()
    counter = 1
    menu_options = [f'{lecture.name}' for lecture in lectures]

    selected_lecture = option_menu(
        "Список лекций",
        menu_options,
        icons=["book"] * len(menu_options),
        menu_icon="bi-book-half",
        default_index=0,
    )

    for lecture in lectures:
        if selected_lecture == f'{lecture.name}':
            st.markdown(lecture.text_material, unsafe_allow_html=True)
            new_students_lessons = StudentLesson(
                student_id=user.student_id,
                lesson_id=lecture.lesson_id
            )
            db.add(new_students_lessons)
            db.commit()
            st.write("<hr>", unsafe_allow_html=True)
    db.close()
    st.header("Дополнительные лекции сгенерированные нейросетью")
    st.write("Будьте осторожны, нейросеть может совершать ошибки, сравнивайте данные сгенерированные лекции "
             "\nс лекциями из методических изданий")

    db = next(get_db())
    lectures = db.query(Lesson).all()
    for lecture in lectures:
        if st.button(f'{lecture.name}', key=f'{lecture.lesson_id} {lecture.lesson_id} + '):
            message = f'Напиши лекцию на тему {lecture.name}'
            msg = [HumanMessage(f'{message}')]
            giga = GigaChat(
                credentials=auth,
                model='GigaChat:latest',
                verify_ssl_certs=False
            )
            answer = giga(msg)
            st.write(answer.content)
            new_students_lessons = StudentLesson(
                student_id=user.student_id,
                lesson_id=lecture.lesson_id
            )
            db.add(new_students_lessons)
            db.commit()
        st.write("<hr>", unsafe_allow_html=True)
    db.close()


# Страница лекций учителя
def show_lecture_page_teacher():
    st.markdown(
        """
        <style>
        .title {
            text-align: center;
        }
        </style>
        <h1 class="title">Лекции</h1>
        """,
        unsafe_allow_html=True
    )
    selected_options = st.selectbox("Выбрана возможность:", ["Просмотр лекций", "Добавление лекций"])
    if selected_options == "Просмотр лекций":
        st.header("Просмотр лекций")
        db = next(get_db())
        lectures = db.query(Lesson).all()
        counter = 1
        menu_options = [f'{lecture.name}' for lecture in lectures]


        selected_lecture = option_menu(
            "Список лекций",
            menu_options,
            icons=["book"] * len(menu_options),
            menu_icon="bi-book-half",
            default_index=0,
            )

        for lecture in lectures:
            if selected_lecture == f'{lecture.name}':
                st.markdown(lecture.text_material, unsafe_allow_html=True)
                st.write("<hr>", unsafe_allow_html=True)


        for lecture in lectures:
            if st.button(f'Удалить лекцию {lecture.name}', key=f'({lecture.lesson_id} + {counter}'):
                db.query(StudentLesson).filter_by(lesson_id=lecture.lesson_id).delete()
                db.query(Lesson).filter_by(lesson_id=lecture.lesson_id).delete()
                db.commit()
                st.rerun()
            st.write("<hr>", unsafe_allow_html=True)
        db.close()
        st.header("Дополнительные лекции сгенерированные нейросетью gigachat")
        st.write("Будьте осторожны, нейросеть может совершать ошибки, сравнивайте данные сгенерированные лекции "
                 "\nс лекциями из методических изданий")

        db = next(get_db())
        lectures = db.query(Lesson).all()
        for lecture in lectures:
            if st.button(f'{lecture.name}', key=f'{lecture.lesson_id} {lecture.lesson_id} + '):
                message = f'Ты ведешь лекции в университете, расскажи лекцию на тему {lecture.name}'
                msg = [langchain.schema.HumanMessage(f'{message}')]
                giga = GigaChat(
                    credentials=auth,
                    model='GigaChat:latest',
                    verify_ssl_certs=False
                )
                answer = giga(msg)
                st.write(answer.content)
            st.write("<hr>", unsafe_allow_html=True)
        db.close()
    elif selected_options == "Добавление лекций":
        st.header("Добавление лекций")
        generate_lecture_constructor()


# Страница тестов ученика
def show_tests_page_stud():
    st.markdown(
        """
        <style>
        .title {
            text-align: center;
        }
        </style>
        <h1 class="title">Тесты</h1>
        """,
        unsafe_allow_html=True
    )
    db = next(get_db())
    lectures = db.query(Lesson).all()
    theme_test = [f'{lecture.name}' for lecture in lectures]
    selected_test = st.selectbox("Выберите тему теста", theme_test)
    selected_type = st.selectbox("Выберите тип теста", ["Сгенерированный тест", "Стандартный тест"])
    for lecture in lectures:
        if selected_test == lecture.name:
            if selected_type == "Сгенерированный тест":
                st.header(f'{lecture.name}')
                if st.button(f'Пройти тест по теме \"{lecture.name}\"'):
                    st.session_state.starting = True
                    st.session_state.is_started = False
                if st.session_state.starting:
                    if not st.session_state.is_started:
                        with st.form("Тест по теме \"Диаграммы ДКА\""):
                            generate_question_image_submit()
                    else:
                        # st.write("Ответы: ", {k: v for k, v in st.session_state.responses.items() if v})
                        counter = 0
                        filtered_dict = {k: v for k, v in st.session_state.responses.items() if v}
                        for k in filtered_dict.keys():
                            key_t, val_i = parse_key(k)
                            img_id_from_i = get_image_id_by_url(val_i)
                            val_id_from_t = get_value_id_by_text(key_t)
                            img_id_from_t = get_option_key_img_id_by_value_id(val_id_from_t)
                            if img_id_from_i == img_id_from_t:
                                counter = counter + 1
                        if counter > 2:
                            st.success(f"{counter} из 5 вопросов решено верно")
                        elif counter == 0:
                            st.error(f"{counter} из 5 вопросов решено верно")
                        else:
                            st.warning(f"{counter} из 5 вопросов решено верно")
                        db = next(get_db())
                        new_test = Test(
                            name=f'{lecture.name}',
                            test_type="Сгенерированный тест",
                            score=counter,
                            datetime=datetime.now(),
                            student_id=user.student_id
                        )
                        db.add(new_test)
                        db.commit()
                        counter = db.query(func.count(Test.test_id)).scalar()
                        counter_quest = db.query(func.count(Quest.quest_id)).scalar()
                        db.close()
                        i = 1
                        for question in st.session_state.questions:
                            if question["type"] == "image":
                                options = " ".join(question["content"]["options"])
                                db = next(get_db())
                                new_quest = Quest(
                                    issue=question["content"]["image"],
                                    options=options
                                )
                                db.add(new_quest)
                                db.commit()
                                new_test_question = TestQuest(
                                    test_id=counter,
                                    quest_id=(counter_quest + i)
                                )
                                db.add(new_test_question)
                                db.commit()
                            else:
                                options = " ".join(question["content"]["options"])
                                db = next(get_db())
                                new_quest = Quest(
                                    issue=question['content']['text'],
                                    options=options
                                )
                                db.add(new_quest)
                                db.commit()
                                new_test_question = TestQuest(
                                    test_id=counter,
                                    quest_id=counter_quest + i
                                )
                                db.add(new_test_question)
                                db.commit()
                            i += 1
                        db.commit()
                        db.close()
                        st.session_state.responses = {}
                        st.session_state.questions = []
            else:
                pass



# Страница тестов учителя
def show_tests_page_teacher():
    st.markdown(
        """
        <style>
        .title {
            text-align: center;
        }
        </style>
        <h1 class="title">Тесты</h1>
        """,
        unsafe_allow_html=True
    )
    selected_options = st.selectbox("Выбрана возможность:", ["Просмотр тестов", "Добавление пар для генерации",
                                                             "Просмотр добавленных пар",
                                                             "Добавление стандартных вопросов"])

    if selected_options == "Просмотр тестов":
        db = next(get_db())
        lectures = db.query(Lesson).all()
        theme_test = [f'{lecture.name}' for lecture in lectures]
        selected_test = st.selectbox("Выберите тему теста", theme_test)
        selected_type = st.selectbox("Выберите тип теста", ["Сгенерированный тест", "Стандартный тест"])
        for lecture in lectures:
            if selected_test == lecture.name:
                if selected_type == "Сгенерированный тест":
                    st.header(f'Тест по теме \"{lecture.name}\"')
                    if st.button(f'Пройти тест по теме \"{lecture.name}\"'):
                        st.session_state.starting = True
                        st.session_state.is_started = False
                    if st.session_state.starting:
                        if not st.session_state.is_started:
                            with st.form("Тест"):
                                generate_question_image_submit()
                        else:
                            # st.write("Ответы: ", {k: v for k, v in st.session_state.responses.items() if v})
                            counter = 0
                            filtered_dict = {k: v for k, v in st.session_state.responses.items() if v}
                            for k in filtered_dict.keys():
                                key_t, val_i = parse_key(k)
                                img_id_from_i = get_image_id_by_url(val_i)
                                val_id_from_t = get_value_id_by_text(key_t)
                                img_id_from_t = get_option_key_img_id_by_value_id(val_id_from_t)
                                if img_id_from_i == img_id_from_t:
                                    counter = counter + 1
                            st.write(f"Вы решили {counter} из 5 вопросов")
                            st.session_state.responses = {}
                            st.session_state.questions = []
                else:
                    pass

    elif selected_options == "Добавление пар для генерации":
        st.title("Выберите тему для вопросов")

        db = next(get_db())
        lessons = db.query(Lesson).all()
        menu_options = [f'{lecture.name}' for lecture in lessons]
        selected_theme = st.selectbox("Выбрана тема:", menu_options)

        if "uploaded_image" not in st.session_state:
            st.session_state.uploaded_image = None
            st.session_state.image_name = None
        col1, col2 = st.columns(2)
        with col1:
            uploaded_file = st.file_uploader("Выберите изображение для пары", type=["jpg", "jpeg", "png"])
            st.text_area("Введите вопрос для ключа")
            if uploaded_file is not None:
                st.session_state.uploaded_image = uploaded_file.read()
                st.session_state.image_name = uploaded_file.name
                st.image(st.session_state.uploaded_image, caption="Предварительный просмотр изображения")
        with col2:
            text_value1 = st.text_area("Введите значение текст для пары")
            st.text_area("Введите вопрос для значения пары")
        if st.button("Добавить пару в базу"):
            if st.session_state.uploaded_image is not None and text_value1:
                try:
                        image_url = upload_image_to_yandex_cloud(st.session_state.uploaded_image,
                                                                 st.session_state.image_name)
                        if image_url:
                            save_option_key_image(image_url, user.teacher_id)
                            save_option_value(text_value1, user.teacher_id, image_url)
                            st.session_state.uploaded_image = None
                            st.session_state.image_name = None
                            st.success("Пара успешно добавлена в базу!")
                except Exception as e:
                    st.error(f"Ошибка при добавлении пары в базу: {e}")
            else:
                st.error("Пожалуйста, загрузите изображение и введите текст.")

    elif selected_options == "Просмотр добавленных пар":
        st.header("Пары")
        st.text("Вы можете удалить выбранную пару")
        st.write("<hr>", unsafe_allow_html=True)
        images = get_all_images()
        values = get_all_values_images()
        counter = 1
        for image, value in zip(images, values):
            col1, col2, col3 = st.columns([3, 2, 2])
            col1.image(fetch_image_from_url(image.content),
                       width=200, use_column_width=True)
            with col2:
                st.write(f"{value.content}")
            with col3:
                if st.button(f"удалить пару {counter}"):
                    if delete_option_value(value.option_value_id):
                        delete_option_key_image(image.option_key_id)
                    st.rerun()
            st.write("<hr>", unsafe_allow_html=True)  # Вывод горизонтальной линии
            counter = counter + 1
    elif selected_options == "Добавление стандартных вопросов":
        st.title("Выберите тему для вопросов")
        db = next(get_db())
        lessons = db.query(Lesson).all()
        menu_options = [f'{lecture.name}' for lecture in lessons]
        selected_theme = st.selectbox("Выбрана тема:", menu_options)
        col1, col2 = st.columns(2)
        with col1:
            st_quill(key="quill2", placeholder="Введите вопрос здесь...", html=True)
        with col2:
            st.text_input(label="1 опция", placeholder="Введите опцию ответа", key=1)
            st.text_input(label="2 опция", placeholder="Введите опцию ответа", key=2)
            st.text_input(label="3 опция", placeholder="Введите опцию ответа", key=3)
            st.text_input(label="4 опция", placeholder="Введите опцию ответа", key=4)
        with col2:
            st.number_input("Верная опция под номером:", value=1, min_value=1, max_value=4)
        st.button("Добавить вопрос в базу")


# Страница личных данных ученика
def show_personal_page_stud():
    st.header(f"Добро пожаловать, студент {user.first_name}!")
    st.header("Ваши данные:")
    st.text("Для изменения данных напишите \nновые значения и нажмите \nна кнопку обновления")
    first_name_change = st.text_input(label="Имя", value=user.first_name)
    second_name_change = st.text_input(label="Фамилия", value=user.second_name)
    email_change = st.text_input(label="Email", value=user.email)
    group_name_change = st.text_input(label="Название группы", value=get_group_name_by_id(user.group_id))
    if st.button("Обновить данные"):
        success1 = assign_group_to_student(student_id=user.student_id,
                                           group_id=get_group_id_by_name(group_name_change))
        success2 = assign_data_to_student(student_id=user.student_id,
                                          first_name=first_name_change,
                                          second_name=second_name_change,
                                          email=email_change)
        if success2 and success1:
            user.group_id = get_group_id_by_name(group_name_change)
            user.first_name = first_name_change
            user.second_name = second_name_change
            user.email = email_change
            st.session_state['user'] = user
            st.success("Данные успешно обновлены")
        elif success2:
            user.first_name = first_name_change
            user.second_name = second_name_change
            user.email = email_change
            st.session_state['user'] = user
            st.success("Данные обновлены частично")
            st.error("Не получилось обновить группу")
        else:
            st.error("Не получилось обновить данные")

    st.header("Изменить пароль:")
    col1, col2 = st.columns(2)
    with col1:
        old_pass = st.text_input(label="Введите старый пароль", type="password")
    with col2:
        new_pass = st.text_input(label="Введите новый пароль", type="password")
    if st.button("Обновить пароль"):
        db = next(get_db())
        student = db.query(Student).filter_by(student_id=user.student_id).first()
        if student:
            # Убедимся, что хранимый пароль - это байты
            if isinstance(student.password, str):
                hashed_password = student.password.encode('utf-8')
            else:
                hashed_password = student.password

            # Проверка старого пароля
            right_pass = check_password(old_pass, hashed_password)

            if right_pass:
                if new_pass:
                    hash_pass = hash_password(new_pass)
                    student.password = hash_pass.decode('utf-8')
                    db.commit()
                    st.session_state['user'] = user
                    st.success("Пароль обновлен")
                else:
                    st.error("Новый пароль не может быть пустым.")
            else:
                st.error("Старый пароль неверный.")
        else:
            st.error("Не удалось найти студента.")


# Страница личных данных учителя
def show_personal_page_teacher():
    st.header(f"Добро пожаловать, преподаватель {user.first_name}!")
    st.header("Ваши данные:")
    st.text("Для изменения данных напишите \nновые значения и нажмите \nна кнопку обновления")
    first_name_change = st.text_input(label="Имя", value=user.first_name)
    second_name_change = st.text_input(label="Фамилия", value=user.second_name)
    email_change = st.text_input(label="Email", value=user.email)
    if st.button("Обновить данные"):
        success = assign_data_to_teacher(teacher_id=user.teacher_id,
                                         first_name=first_name_change,
                                         second_name=second_name_change,
                                         email=email_change)
        if success:
            st.success("Данные обновлены")
            user.first_name = first_name_change
            user.second_name = second_name_change
            user.email = email_change
            st.session_state['user'] = user
        else:
            st.error("Не получилось обновить данные")
    st.header("Изменить пароль:")
    col1, col2 = st.columns(2)
    with col1:
        old_pass = st.text_input(label="Введите старый пароль", type="password")
    with col2:
        new_pass = st.text_input(label="Введите новый пароль", type="password")
    if st.button("Обновить пароль"):
        db = next(get_db())
        teacher = db.query(Teacher).filter_by(teacher_id=user.teacher_id).first()
        if teacher:
            # Убедимся, что хранимый пароль - это байты
            if isinstance(teacher.password, str):
                hashed_password = teacher.password.encode('utf-8')
            else:
                hashed_password = teacher.password

            # Проверка старого пароля
            right_pass = check_password(old_pass, hashed_password)
            if right_pass:
                if new_pass:
                    hash_pass = hash_password(new_pass)
                    teacher.password = hash_pass.decode('utf-8')
                    db.commit()
                    st.session_state['user'] = user
                    st.success("Пароль обновлен")
                else:
                    st.error("Новый пароль не может быть пустым.")
            else:
                st.error("Старый пароль неверный.")
        else:
            st.error("Не удалось найти студента.")


# Страница статистики ученика
def show_statistic_stud():
    st.markdown(
        """
        <style>
        .title {
            text-align: center;
        }
        </style>
        <h1 class="title">Статистика</h1>
        """,
        unsafe_allow_html=True
    )
    db = next(get_db())
    const_suc = 2
    count_lectures = db.query(func.count(distinct(StudentLesson.lesson_id))).filter_by(student_id=user.student_id).scalar()
    count_all_lectures = db.query(func.count(Lesson.lesson_id)).scalar()
    count_attempts = db.query(func.count(Test.test_id)).filter_by(student_id=user.student_id).scalar()
    count_success_attempts = db.query(func.count(Test.test_id)).filter(
        Test.student_id == user.student_id).filter(cast(Test.score, Integer) >= const_suc).scalar()
    count_success_themes_test = db.query(func.count(distinct(Test.name))).filter(
        and_(Test.student_id == user.student_id, cast(Test.score, Integer) >= const_suc)).scalar()
    count_all_themes_test = db.query(func.count(distinct(Test.name))).scalar()
    average_score = round(db.query(func.avg(cast(Test.score, Integer))).filter(
        Test.student_id == user.student_id).scalar(), 2)
    st.header("Общая статистика")
    st.write(f'Пройденных лекций: {count_lectures} из {count_all_lectures}')
    st.write(f'Попыток пройти тесты: {count_attempts}')
    st.write(f'Успешных попыток тестов: {count_success_attempts}')
    st.write(f'Успешно пройденных тем тестов: {count_success_themes_test} из {count_all_themes_test}')
    st.write(f'Средний балл за тесты: {average_score}')
    st.header("Ваши попытки пройти тесты")
    stud_tests = db.query(Test).filter_by(student_id=user.student_id).all()
    data = [{
        'Идентификатор': test.test_id,
        'Тема': test.name,
        'Результат': test.score,
        'Дата прохождения': test.datetime,
        'Тип': test.test_type
    }
        for test in stud_tests
    ]
    db.close()
    df = pd.DataFrame(data)
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_pagination(paginationAutoPageSize=True)  # Добавление пагинации
    gb.configure_default_column(editable=False, filter=True)  # Фильтрация и редактирование
    grid_options = gb.build()
    AgGrid(df, gridOptions=grid_options)

    st.header("Детали попыток")
    col1, col2 = st.columns([2, 5])
    with col1:
        test_id = st.number_input('Введите идентификатор теста', min_value=1)
    test_quests = get_questions_by_test_id(test_id)
    # Отображение вопросов
    if test_quests:
        st.write(f'Вопросы теста с идентификатором {test_id}:')
        for quest in test_quests:
            str = quest.issue
            opt = quest.options

            if str.startswith("https"):
                opt_arr = opt.split()
                col1, col2 = st.columns(2)
                with col1:
                    st.write("Дана диаграмма ДКА, на которой зеленым треугольником отмечено начальное состояние, " +
                             "\nа красным шестиугольником отмечено(ы) заключительное(ые) состояние(я). " +
                             "\nВыяснить какое слово будет допущено этим автоматом.")
                    st.image(fetch_image_from_url(str))
                with col2:
                    st.write(f'Варианты ответов: \n')
                    for opt in opt_arr:
                        st.write(f'{opt}')
                st.write("<hr>", unsafe_allow_html=True)
            else:
                opt_arr = opt.split()
                col1, col2 = st.columns(2)
                with col1:
                    st.write("Выяснить какой ДКА допустит это слово. " +
                             "\nНа диаграммах ДКА зелеными треугольниками отмечаются начальные состояния," +
                             "\nкрасными шестиугольниками – заключительные.")
                    st.write(f'{str}')
                with col2:
                    st.write(f'\nВарианты ответов:')
                    for opt in opt_arr:
                        st.image(fetch_image_from_url(opt))
                st.write("<hr>", unsafe_allow_html=True)
    else:
        st.write('Нет вопросов для указанного теста.')


# Страница статистики для учителя
def show_statistic_teacher():
    st.markdown(
        """
        <style>
        .title {
            text-align: center;
        }
        </style>
        <h1 class="title">Статистика</h1>
        """,
        unsafe_allow_html=True
    )
    db = next(get_db())
    student_test_data = db.query(
        Student.student_id,
        Student.first_name,
        Student.second_name,
        Group.name.label('group_name'),
        func.count(distinct(Test.name)).label('unique_tests_passed'),
        func.round(func.avg(cast(Test.score, Integer)), 2).label('average_score')
    ).join(
        Test, Student.student_id == Test.student_id
    ).join(
        Group, Student.group_id == Group.group_id
    ).filter(
        cast(Test.score, Integer) > 1
    ).group_by(
        Student.student_id, Student.first_name, Student.second_name, Group.name
    ).all()

    # Формирование данных для отображения
    data = [{
        'ID': f'{student_id}',
        'Студент': f'{first_name} {second_name}',
        'Группа': group_name,
        'Количество успешно пройденных тестов': unique_tests_passed,
        'Средний балл': average_score
    } for student_id, first_name, second_name, group_name, unique_tests_passed, average_score in student_test_data]
    df = pd.DataFrame(data)
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_default_column(editable=False, filter=True)
    grid_options = gb.build()
    AgGrid(df, gridOptions=grid_options)
    db.close()

    st.header("Подробности каждой попытки")
    db = next(get_db())
    stud_tests = db.query(Test).all()
    data = [{
        'ID Студента': test.student_id,
        'Идентификатор попытки': test.test_id,
        'Тема': test.name,
        'Результат': test.score,
        'Дата прохождения': test.datetime,
        'Тип': test.test_type
    }
        for test in stud_tests
    ]
    db.close()
    df = pd.DataFrame(data)
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_pagination(paginationAutoPageSize=True)  # Добавление пагинации
    gb.configure_default_column(editable=False, filter=True)  # Фильтрация и редактирование
    grid_options = gb.build()
    AgGrid(df, gridOptions=grid_options)


# Страница учеников (для учителей)
def show_students_page():
    st.markdown(
        """
        <style>
        .title {
            text-align: center;
        }
        </style>
        <h1 class="title">Студенты и группы</h1>
        """,
        unsafe_allow_html=True
    )
    selected_action = st.selectbox("Выбрана возможность:", ["Изменение группы студенту", "Добавление групп"])
    if selected_action == "Изменение группы студенту":
        st.header("Изменение группы")
        col4, col5 = st.columns(2)
        with col4:
            student_id = st.number_input("Студенту с ID: ", min_value=0, step=1, format="%d")
        with col5:
            group_id = st.number_input("Назначить группу с ID: ", min_value=0, step=1, format="%d")
        if st.button("Назначить группу студенту"):
            success = assign_group_to_student(student_id=student_id, group_id=group_id)
            if success:
                st.success(f"Группа с ID {group_id} успешно назначена студенту с ID {student_id}")
                st.rerun()
            else:
                st.error("Не удалось найти студента с таким ID")
        all_groups_table()
        students_table()

    elif selected_action == "Добавление групп":
        st.header("Добавить группу")
        group_name = st.text_input("Название группы")
        date_start = st.date_input("Дата начала")
        date_end = st.date_input("Дата окончания")
        if st.button("Добавить группу"):
            if group_name and date_start and date_end:
                db = next(get_db())
                new_group = Group(name=group_name, date_start=date_start, date_end=date_end)
                db.add(new_group)
                db.commit()
                db.refresh(new_group)
                st.success(f"Группа {group_name} добавлена с ID {new_group.group_id}")
            else:
                st.error("Пожалуйста, заполните все поля.")


#
# Начало приложения
#
# st.title("Электронный учебник по теории разработки компиляторов")
#


# Проверка авторизации и роли пользователя
if 'user' in st.session_state and 'is_teacher' in st.session_state:
    user = st.session_state['user']
    is_teacher = st.session_state['is_teacher']
    if is_teacher:
        selected_page = st.sidebar.radio("Навигация",
                                         ["Личные данные", "Статистика", "Лекции", "Тесты", "Студенты и группы"])
        if selected_page == "Личные данные":
            show_personal_page_teacher()
        if selected_page == "Статистика":
            show_statistic_teacher()
        if selected_page == "Лекции":
            show_lecture_page_teacher()
        if selected_page == "Тесты":
            show_tests_page_teacher()
        if selected_page == "Студенты и группы":
            show_students_page()
        st.sidebar.text(f"{user.first_name} {user.second_name}")
    else:
        selected_page = st.sidebar.radio("Навигация", ["Личные данные", "Статистика", "Лекции", "Тесты"])
        if selected_page == "Личные данные":
            show_personal_page_stud()
        if selected_page == "Статистика":
            show_statistic_stud()
        if selected_page == "Лекции":
            show_lecture_page_stud()
        if selected_page == "Тесты":
            show_tests_page_stud()
        st.sidebar.text(f"{user.first_name} {user.second_name}")
    if st.sidebar.button("Выйти"):
        st.session_state.pop('user', None)
        st.session_state.pop('is_teacher', None)
        st.session_state.starting = False
        st.session_state.blocks = []
        st.rerun()
else:
    show_registration_page()
