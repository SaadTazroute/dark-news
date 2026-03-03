# ─── CloudWatch Log Groups ────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "health_lambda" {
  name              = "/aws/lambda/dark-web-newsletter-health"
  retention_in_days = 180
}

# ─── Lambda — /health endpoint ───────────────────────────────────────────────

resource "aws_lambda_function" "health" {
  function_name = "dark-web-newsletter-health"
  role          = aws_iam_role.lambda_exec.arn
  runtime       = "python3.12"
  handler       = "handler.handler"
  filename      = var.health_lambda_zip
  timeout       = 10
  memory_size   = 128

  environment {
    variables = {
      RUN_HISTORY_TABLE = aws_dynamodb_table.run_history.name
      AWS_REGION        = var.aws_region
    }
  }

  tracing_config {
    mode = "Active"
  }

  depends_on = [aws_cloudwatch_log_group.health_lambda]
}

# ─── API Gateway — /health ────────────────────────────────────────────────────

resource "aws_apigatewayv2_api" "health" {
  name          = "dark-web-newsletter-health"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "health" {
  api_id                 = aws_apigatewayv2_api.health.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.health.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.health.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.health.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.health.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.health_lambda.arn
  }
}

resource "aws_lambda_permission" "apigw_health" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.health.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.health.execution_arn}/*/*"
}

# ─── EventBridge — daily pipeline schedule ───────────────────────────────────

resource "aws_cloudwatch_event_rule" "daily_pipeline" {
  name                = "dark-web-newsletter-daily"
  description         = "Triggers the newsletter pipeline daily"
  schedule_expression = var.schedule_expression
}

# Note: The orchestrator runs as an AgentCore job. The EventBridge rule target
# points to the AgentCore job ARN once deployed. Placeholder target below —
# replace with actual AgentCore job ARN after first AgentCore deployment.
resource "aws_cloudwatch_event_target" "pipeline" {
  rule      = aws_cloudwatch_event_rule.daily_pipeline.name
  target_id = "NewsletterPipeline"
  arn       = var.agentcore_job_arn

  # Pass the AWS region as input to the job
  input = jsonencode({ aws_region = var.aws_region })
}
