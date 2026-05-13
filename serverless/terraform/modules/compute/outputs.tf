output "api_gateway_url" {
  description = "API Gateway invoke URL"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "api_gateway_id" {
  value = aws_apigatewayv2_api.main.id
}

output "lambda_function_name" {
  value = aws_lambda_function.app.function_name
}
