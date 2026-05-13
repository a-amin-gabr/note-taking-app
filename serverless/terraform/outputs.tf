output "app_url" {
  description = "Application URL"
  value       = "https://${var.app_domain}"
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (for cache invalidation)"
  value       = module.cdn.cloudfront_distribution_id
}

output "api_gateway_url" {
  description = "API Gateway invoke URL"
  value       = module.compute.api_gateway_url
}

output "dynamodb_table" {
  description = "DynamoDB table name"
  value       = module.database.table_name
}

output "static_bucket" {
  description = "S3 bucket for static assets"
  value       = module.storage.static_bucket_name
}
