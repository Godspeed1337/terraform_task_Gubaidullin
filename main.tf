terraform {
  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
    }
  }
  required_version = ">= 0.13"
}

provider "yandex" {
  service_account_key_file = "key.json"
  cloud_id                 = var.cloud_id
  folder_id                = var.folder_id
  zone                     = var.zone
}

resource "yandex_iam_service_account_static_access_key" "sa-static-key" {
 service_account_id = var.service_acc_id
 description        = "for obj storage"
 }

resource "yandex_iam_service_account_api_key" "sa-api-key" {
  service_account_id = var.service_acc_id
  description        = "for yandex vision"
}


resource "yandex_storage_bucket" "photo" {
  access_key = yandex_iam_service_account_static_access_key.sa-static-key.access_key
  secret_key = yandex_iam_service_account_static_access_key.sa-static-key.secret_key
  bucket     = "vvot11-photo"
  max_size   = var.bucket_size
  default_storage_class = "STANDARD"
}

resource "yandex_storage_bucket" "face" {
  access_key = yandex_iam_service_account_static_access_key.sa-static-key.access_key
  secret_key = yandex_iam_service_account_static_access_key.sa-static-key.secret_key
  bucket     = "vvot11-faces"
  max_size   = var.bucket_size
  default_storage_class = "STANDARD"
}

resource "yandex_message_queue" "queue-task" {
  name                        = "vvot11-task"
  visibility_timeout_seconds  = 30
  receive_wait_time_seconds   = 20
  message_retention_seconds   = 1209600
  access_key = yandex_iam_service_account_static_access_key.sa-static-key.access_key
  secret_key = yandex_iam_service_account_static_access_key.sa-static-key.secret_key
}

resource "yandex_ydb_database_serverless" "db-photo-face" {
  name      = "vvot11-db-photo-face"
  deletion_protection = false
}

resource "yandex_ydb_table" "photos_table" {
  path = "photos"
  connection_string = yandex_ydb_database_serverless.db-photo-face.ydb_full_endpoint

  column {
      name = "copy"
      type = "string"
    }
  column {
      name = "original"
      type = "string"
    }
  column {
      name = "name"
      type = "string"
    }

  primary_key = ["copy"]

}


resource "archive_file" "detectionzip" {
  output_path = "detection.zip"
  type        = "zip"
  source_dir  = "detection"
}

resource "yandex_function" "detection" {
  name               = "vvot11-face-detection"
  user_hash          = "any_string"
  runtime            = "python312"
  entrypoint         = "index.handler"
  memory             = "128"
  execution_timeout  = "10"
  service_account_id = var.service_acc_id
  content {
    zip_filename = "detection.zip"
  }
  environment = {
    AWS_ACCESS_KEY_ID = yandex_iam_service_account_static_access_key.sa-static-key.access_key
    AWS_SECRET_ACCESS_KEY = yandex_iam_service_account_static_access_key.sa-static-key.secret_key
    YMQ_QUEUE_URL = yandex_message_queue.queue-task.id
    AWS_DEFAULT_REGION = var.default_region
    API_KEY = yandex_iam_service_account_api_key.sa-api-key.secret_key
  }
}

resource "archive_file" "cutzip" {
  output_path = "cut.zip"
  type        = "zip"
  source_dir  = "cut"
}

resource "yandex_function" "cut" {
  name               = "vvot11-face-cut"
  user_hash          = "any_string"
  runtime            = "python312"
  entrypoint         = "index.handler"
  memory             = "128"
  execution_timeout  = "30"
  service_account_id = var.service_acc_id
  content {
    zip_filename = "cut.zip"
  }
  environment = {
    AWS_ACCESS_KEY_ID = yandex_iam_service_account_static_access_key.sa-static-key.access_key
    AWS_SECRET_ACCESS_KEY = yandex_iam_service_account_static_access_key.sa-static-key.secret_key
    BUCKET_NAME = yandex_storage_bucket.face.bucket
    YDB_ENDPOINT = "grpcs://${yandex_ydb_database_serverless.db-photo-face.ydb_api_endpoint}"
    YDB_DATABASE = yandex_ydb_database_serverless.db-photo-face.database_path
  }
}


resource "yandex_api_gateway" "face-api-gateway" {
  name        = "vvot11-apigw"
  description = "Serve photos from Yandex Cloud Object Storage"
  spec        = <<-EOT
    openapi: 3.0.0
    info:
      title: Sample API
      version: 1.0.0

    paths:
      /:
        get:
          summary: Serve static file from Yandex Cloud Object Storage
          parameters:
            - name: face
              in: query
              required: true
              schema:
                type: string
          x-yc-apigateway-integration:
            type: object_storage
            bucket: ${yandex_storage_bucket.face.bucket}
            object: '{face}'
            service_account_id: ${var.service_acc_id}
  EOT
}

resource "yandex_function_trigger" "photo_trigger" {
  name        = "vvot11-photo"
  object_storage {
     bucket_id = yandex_storage_bucket.photo.id
     create    = true
     suffix    = "jpg"
     batch_cutoff = 30
  }
  function {
    id                 = yandex_function.detection.id
    service_account_id = var.service_acc_id
    tag = "$latest"
  }
}

resource "yandex_function_trigger" "task_trigger" {
  name        = "vvot11-task"
  message_queue {
    queue_id           = yandex_message_queue.queue-task.arn
    service_account_id = var.service_acc_id
    batch_size         = "1"
    batch_cutoff       = "10"
  }
  function {
    id = yandex_function.cut.id
    service_account_id = var.service_acc_id
    tag = "$latest"
  }
}

resource "archive_file" "tgzip" {
  output_path = "bot.zip"
  type        = "zip"
  source_dir  = "bot"
}

resource "yandex_function" "bot" {
  name               = "vvot11-2023-boot"
  user_hash          = "any_string3"
  runtime            = "python312"
  entrypoint         = "index.handler"
  memory             = "128"
  execution_timeout  = "10"
  service_account_id = var.service_acc_id
  content {
    zip_filename = "bot.zip"
  }
  environment = {
    TGKEY = var.tgkey
    YDB_DATABASE = yandex_ydb_database_serverless.db-photo-face.database_path
    API_GATEWAY_KEY = yandex_api_gateway.face-api-gateway.id
    YDB_ENDPOINT = "grpcs://${yandex_ydb_database_serverless.db-photo-face.ydb_api_endpoint}"
  }
}

resource "yandex_function_iam_binding" "bot-public" {
  function_id = yandex_function.bot.id
  role        = "serverless.functions.invoker"

  members = [
    "system:allUsers",
  ]
}

data "http" "webhook" {
  url = "https://api.telegram.org/bot${var.tgkey}/setWebhook?url=https://functions.yandexcloud.net/${yandex_function.bot.id}"
}