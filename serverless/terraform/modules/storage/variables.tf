variable "project_name" {
  description = "Project name for bucket naming"
  type        = string
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
