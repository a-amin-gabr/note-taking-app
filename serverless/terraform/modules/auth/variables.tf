variable "project_name" {
  description = "Project name"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "app_domain" {

  description = "Application domain"
  type        = string
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

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}

