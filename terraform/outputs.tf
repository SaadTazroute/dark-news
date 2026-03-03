output "health_api_url" {
  description = "URL of the /health endpoint"
  value       = "${aws_apigatewayv2_stage.default.invoke_url}/health"
}

output "config_table_name" {
  description = "DynamoDB config table name"
  value       = aws_dynamodb_table.config.name
}

output "run_history_table_name" {
  description = "DynamoDB run history table name"
  value       = aws_dynamodb_table.run_history.name
}

output "dashboard_url" {
  description = "CloudWatch Dashboard URL"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

output "secret_name" {
  description = "Secrets Manager secret name for credentials"
  value       = aws_secretsmanager_secret.credentials.name
}
