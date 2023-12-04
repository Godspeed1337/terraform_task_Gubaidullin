import json
import os
import uuid
import ydb
import boto3
import cv2
import numpy as np
import requests
import random


boto_session = None
storage_client = None
ydb_driver = None


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


def get_storage_client():
    global storage_client
    if storage_client is not None:
        return storage_client

    storage_client = get_boto_session().client(
        service_name='s3',
        endpoint_url='https://storage.yandexcloud.net',
        region_name='ru-central1'
    )
    return storage_client

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


def draw_face(file, coords):
    coords_list = []
    for coord in coords:
        x = coord["x"]
        y = coord["y"]
        coords_list.append([x, y])
    rect_coords = np.array(coords_list, dtype=np.int32)
    rect_coords = rect_coords.reshape((-1, 1, 2))
    jpg_as_np = np.frombuffer(file.read(), dtype=np.uint8)
    img = cv2.imdecode(jpg_as_np, flags=1)
    cv2.polylines(img, [rect_coords], isClosed=True, color=(0, 0, 255), thickness=2)
    return img


def add_to_db(orig_name, processed_name):
    driver = get_ydb_driver()
    with driver:
        driver.wait(fail_fast=True, timeout=15)
        session = driver.table_client.session().create()
        session.transaction().execute(
            f"INSERT INTO photos (original, copy) VALUES ('{orig_name}', '{processed_name}');", commit_tx=True)


def handler(event, context):
    bucket_with_faces = os.environ['BUCKET_NAME']
    messages = event['messages']
    for message in messages:
        body = json.loads(message['details']['message']['body'])
        bucket_name = body["bucket_id"]
        obj = body['obj']
        coords = body['coords']
        file = get_storage_client().get_object(Bucket=bucket_name, Key=obj)['Body']
        img_with_face = draw_face(file, coords)
        image_string = cv2.imencode('.jpg', img_with_face)[1]
        file_name = f"{obj[:-4]}{random.randint(1,1000000)}.jpg"
        add_to_db(obj, file_name)
        get_storage_client().put_object(Bucket=bucket_with_faces, Key=file_name, Body=bytes(image_string), ContentType='image/jpeg')
    return {
        'statusCode': 200,
        }