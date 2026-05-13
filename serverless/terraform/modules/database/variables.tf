variable "table_name" {
  description = "DynamoDB table name"
  type        = string
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
