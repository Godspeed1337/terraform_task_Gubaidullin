import json
import os
import base64
import requests

import boto3

boto_session = None
ymq_queue = None
storage_client = None


def encode_file(file):
    file_content = file.read()
    return base64.b64encode(file_content)


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


def get_ymq_queue():
    global ymq_queue
    if ymq_queue is not None:
        return ymq_queue

    ymq_queue = get_boto_session().resource(
        service_name='sqs',
        endpoint_url='https://message-queue.api.cloud.yandex.net',
        region_name='ru-central1'
    ).Queue(os.environ['YMQ_QUEUE_URL'])
    return ymq_queue


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


def get_faces(file_photo, folder_id):
    encoded = encode_file(file_photo)
    print(encoded)
    data = {
        "folderId": folder_id,
        "analyze_specs": [{
            "content": str(encoded)[2:-1],
            "features": [{
                "type": "FACE_DETECTION"
            }]
        }]
    }
    API_KEY = os.environ['API_KEY']
    headers = {
        "Authorization": f"Api-Key {API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url="https://vision.api.cloud.yandex.net/vision/v1/batchAnalyze", json=data,
                         headers=headers)
    resp_json = resp.json()
    faces = resp_json['results'][0]['results'][0]['faceDetection']['faces']
    return faces

def handler(event, context):
    messages = event['messages']
    for message in messages:
        details = message['details']
        bucket_name = details['bucket_id']
        obj = details['object_id']
        folder_id = message['event_metadata']['folder_id']
        file = get_storage_client().get_object(Bucket=bucket_name, Key=obj)['Body']
        faces = get_faces(file, folder_id)
        for face in faces:
            coords = face['boundingBox']['vertices']
            get_ymq_queue().send_message(MessageBody=json.dumps({'bucket_id': bucket_name,
                                                                 "obj": obj,
                                                                 "folder_id": folder_id,
                                                                 "coords": coords}))
    return {
        'statusCode': 200,
        }
