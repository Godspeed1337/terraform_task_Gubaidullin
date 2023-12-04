variable "tgkey" {
  type        = string
  description = "Telegram Bot API Key"
}

variable "service_acc_id" {
  type        = string
  description = "service_acc_id"
}

variable "bucket_size" {
  type = number
  description = "bucket_size"
}

variable "default_region" {
  default = "ru-central1"
  type = string
  description = "default_region"
}

variable "cloud_id" {
  type = string
  description = "cloud_id"
}

variable "folder_id" {
  type = string
  description = "folder_id"
}

variable "zone" {
  type = string
  description = "zone"
}
