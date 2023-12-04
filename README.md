# Задание по Облачным технологиям

## Инструкция:

1. Создать сервисный аккаунт с ролью админа
2. Сгенерировать key.json (`yc iam key create --service-account-name my-robot --output key.json`,
подробнее в документации)
3. Нужно создать файл terraform.tfvars со следующими переменными:
   - tgkey - ключ от тг бота
   - service_acc_id - id сервисного аккаунта
   - bucket_size - размер в байтах object storage
   - default_region - дефолтный регион(ru-central1 по умолчанию)
   - cloud_id - id облака
   - folder_id - id папки
   - zone - зона (например ru-central1-a)