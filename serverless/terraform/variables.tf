variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-central-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "notes-app"
}

variable "app_domain" {
  description = "Domain name for the application (e.g. notes.abdallahgabr.me)"
  type        = string
}

variable "root_domain" {
  description = "Root domain for Route 53 zone lookup (e.g. abdallahgabr.me)"
  type        = string
}

variable "lambda_package" {
  description = "Path to the Lambda deployment ZIP file"
  type        = string
  default     = "../package/lambda.zip"
}

variable "secret_key" {
  description = "Flask SECRET_KEY for session encryption"
  type        = string
  sensitive   = true
}

variable "cognito_domain_prefix" {
  description = "Custom prefix for the Cognito Hosted UI domain"
  type        = string
}

variable "google_client_id" {

  description = "Google OAuth Client ID"
  type        = string
}

variable "google_client_secret" {
  description = "Google OAuth Client Secret"
  type        = string
  sensitive   = true
}


