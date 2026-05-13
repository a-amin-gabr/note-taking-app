output "static_bucket_name" {
  value = aws_s3_bucket.static.bucket
}

output "static_bucket_id" {
  value = aws_s3_bucket.static.id
}

output "static_bucket_regional_domain" {
  value = aws_s3_bucket.static.bucket_regional_domain_name
}

output "static_bucket_arn" {
  value = aws_s3_bucket.static.arn
}

output "attachments_bucket_name" {
  value = aws_s3_bucket.attachments.bucket
}

output "attachments_bucket_arn" {
  value = aws_s3_bucket.attachments.arn
}
