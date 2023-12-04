import json
import requests
import os
import boto3
import ydb
import random

TGKEY = os.environ["TGKEY"]
API_GATEWAY_KEY = os.environ["API_GATEWAY_KEY"]
ydb_driver = None
session = boto3.session.Session()
s3 = session.client(
    service_name="s3",
    endpoint_url="https://storage.yandexcloud.net",
)

good_response = {
    'statusCode': 200,
}
bad_response = {
    'statusCode': 500,
}


def generate_im_token():
    url = 'http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token'
    headers = {'Metadata-Flavor': 'Google'}
    resp = requests.get(url, headers=headers)
    return json.loads(resp.content.decode('UTF-8'))['access_token']


def get_boto_session():
    global boto_session
    if boto_session is not None:
        return boto_session
    access_key = os.environ['AWS_ACCESS_KEY_ID']
    secret_key = os.environ['AWS_SECRET_ACCESS_KEY']
    boto_session = boto3.session.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key
    )
    return boto_session


def get_ydb_driver():
    global ydb_driver
    if ydb_driver is not None:
        return ydb_driver

    ydb_driver = ydb.Driver(
        endpoint=os.getenv('YDB_ENDPOINT'),
        database=os.getenv('YDB_DATABASE'),
        credentials=ydb.AccessTokenCredentials(generate_im_token()),
    )
    return ydb_driver


def get_random_unnamed_row(db_name: str = "photos", field_name: str = "name"):
    driver = get_ydb_driver()
    with driver:
        driver.wait(fail_fast=True, timeout=15)
        session = driver.table_client.session().create()
        data = session.transaction().execute(f"SELECT * FROM {db_name} WHERE {db_name}.{field_name} is null")
        photos = []
        for rows in data:
            for row in rows.rows:
                photos.append([row["original"].decode("utf-8"), row["copy"].decode("utf-8")])
        
        if len(photos) == 0:
            return None, None

        return photos[random.randint(0, len(photos) - 1)]


def update_name_in_db(
        new_name: str = "some name",
        pk: str = "name_2",
        db_name: str = "photos",
        field_name: str = "name",
        pk_name: str = "copy"
    ):
    driver = get_ydb_driver()
    with driver:
        driver.wait(fail_fast=True, timeout=15)
        session = driver.table_client.session().create()
        session.transaction().execute(
            f"UPDATE {db_name} set {field_name} = '{new_name}' WHERE {pk_name} = '{pk}'", commit_tx=True)


def get_named_row(value: str = "name", db_name: str = "photos", field_name: str = "name"):
    driver = get_ydb_driver()
    with driver:
        driver.wait(fail_fast=True, timeout=15)
        session = driver.table_client.session().create()
        data = session.transaction().execute(f"SELECT * FROM {db_name} WHERE {db_name}.{field_name} = '{value}'")
        photos = []
        for rows in data:
            for row in rows.rows:
                photos.append([row["original"].decode("utf-8"), row["copy"].decode("utf-8")])

        return photos


def send_message(chat_id, text, *args, **kwargs):
    url = f"https://api.telegram.org/bot{TGKEY}/sendMessage"
    params = kwargs
    params["chat_id"] = chat_id
    params["text"] = text
    r = requests.get(url=url, params = params)


def handler(event, context):
    global good_response, bad_response, s3, TGKEY, API_GATEWAY_KEY
    update = json.loads(event["body"])

    try:
        message = update["message"]
        message_id = message["message_id"]
        chat_id = message["chat"]["id"]
    except:
        return good_response

    replied_message = message.get("reply_to_message", None)
    if replied_message is not None:
        repl_text = replied_message.get("caption", None)
        if repl_text is not None:
            # repl -- image - name \nОтветьте на данное сообщение для настройки имени
            repl_text = repl_text.split(" - ")[-1]
            repl_text = repl_text.split(" \n")[0].strip()
            update_name_in_db(new_name=message.get("text", None), pk=repl_text)
            send_message(chat_id, f"Присвоено новое имя для фотографии - {repl_text}", reply_to_message_id=message_id)
            return

    if "text" in message:
        text = message["text"]
        if "/getface" in text:
            photo_pk, photo_name = get_random_unnamed_row()
            if photo_name is None or photo_name == "":
                send_message(chat_id, f"Нет изображений без имени", reply_to_message_id=message_id)
                return
            
            url = f"https://api.telegram.org/bot{TGKEY}/sendPhoto"
            params = {
                "chat_id": chat_id,
                "photo": f"https://{API_GATEWAY_KEY}.apigw.yandexcloud.net/?face={photo_name}",
                "caption": f"image - {photo_name} \nОтветьте на данное сообщение для настройки имени",
                "reply_to_message_id": message_id,
            }
            r = requests.get(url=url, params=params)
            return good_response
        elif "/find " in text:
            text = text.split("/find ", 1)[1]
            data = get_named_row(text)
            if not data:
                send_message(chat_id, f"Фотографии с {text} не найдены", reply_to_message_id=message_id)
                return

            for element in data:
                photo_pk, photo_name = element[0], element[1]
                url = f"https://api.telegram.org/bot{TGKEY}/sendPhoto"
                params = {
                    "chat_id": chat_id,
                    "photo": f"https://{API_GATEWAY_KEY}.apigw.yandexcloud.net/?face={photo_name}",
                    "caption": f"image - {photo_pk}",
                    "reply_to_message_id": message_id,
                }
                r = requests.get(url=url, params=params)
            return good_response
        
    rep_text = "Ошибка"
    send_message(chat_id, rep_text, reply_to_message_id=message_id)

    # url = f"https://api.telegram.org/bot{TGKEY}/sendMessage"
    # params = {"chat_id": chat_id,
    #          "text": rep_text,
    #          "reply_to_message_id": message_id}
    # r = requests.get(url=url, params = params)
    return good_response


def debug_handler(event, context):
    try:
        return handler(event, context)
    except Exception as e:
        print(f"{type(e)}  ---  {e}")
