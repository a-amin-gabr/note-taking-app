variable "app_domain" {
  type = string
}

variable "api_gateway_url" {
  type = string
}

variable "static_bucket" {
  description = "S3 bucket regional domain name"
  type        = string
}

variable "static_bucket_id" {
  type = string
}

variable "zone_id" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
