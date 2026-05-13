variable "project_name" {
  type = string
}

variable "lambda_package" {
  type = string
}

variable "dynamodb_table" {
  type = string
}

variable "s3_bucket" {
  type = string
}

variable "static_bucket" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "cognito_user_pool_id" {
  type = string
}

variable "cognito_client_id" {
  type = string
}

variable "cognito_client_secret" {
  type      = string
  sensitive = true
}

variable "cognito_domain" {
  type = string
}

variable "secret_key" {
  type      = string
  sensitive = true
}

variable "app_domain" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
