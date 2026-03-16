# ─── S3 bucket — agent code zip ───────────────────────────────────────────────

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "agent_code" {
  bucket        = "early-newsletter-agent-${data.aws_caller_identity.current.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "agent_code" {
  bucket = aws_s3_bucket.agent_code.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "agent_code" {
  bucket = aws_s3_bucket.agent_code.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "agent_code" {
  bucket                  = aws_s3_bucket.agent_code.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ─── Upload pre-built code zip ────────────────────────────────────────────────
# Run scripts/build_agent.sh before terraform apply to generate dist/agent.zip

resource "aws_s3_object" "agent_zip" {
  bucket = aws_s3_bucket.agent_code.id
  key    = "agent.zip"
  source = "${path.module}/../dist/agent.zip"
  etag   = filemd5("${path.module}/../dist/agent.zip")
}

# ─── IAM — AgentCore execution role ───────────────────────────────────────────

data "aws_iam_policy_document" "agentcore_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "agentcore" {
  name               = "early-newsletter-agentcore"
  assume_role_policy = data.aws_iam_policy_document.agentcore_assume.json
}

data "aws_iam_policy_document" "agentcore_policy" {
  statement {
    sid       = "S3Code"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.agent_code.arn}/*"]
  }

  statement {
    sid       = "Bedrock"
    actions   = ["bedrock:InvokeModel"]
    resources = ["*"]
  }

  statement {
    sid = "DynamoDB"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Scan",
      "dynamodb:Query",
    ]
    resources = [
      aws_dynamodb_table.config.arn,
      aws_dynamodb_table.run_history.arn,
    ]
  }

  statement {
    sid       = "SecretsManager"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.credentials.arn]
  }

  statement {
    sid       = "SES"
    actions   = ["ses:SendEmail", "ses:SendRawEmail"]
    resources = ["*"]
  }

  statement {
    sid       = "CloudWatch"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
  }

  statement {
    sid = "Logs"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:*:*:*"]
  }

  statement {
    sid = "XRay"
    actions = [
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "agentcore" {
  name   = "early-newsletter-agentcore-policy"
  role   = aws_iam_role.agentcore.id
  policy = data.aws_iam_policy_document.agentcore_policy.json
}

# ─── CloudWatch Log Group ─────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "agentcore" {
  name              = "/aws/bedrock-agentcore/early-newsletter"
  retention_in_days = 180
}

# ─── AgentCore Runtime — deployed via AWS CLI (Terraform provider support pending) ───

locals {
  # AgentCore runtime name: no hyphens, max 48 chars, must match [a-zA-Z][a-zA-Z0-9_]{0,47}
  agentcore_runtime_name = "EarlyAINewsletter"
}

resource "null_resource" "agentcore_runtime" {
  triggers = {
    agent_zip_md5 = filemd5("${path.module}/../dist/agent.zip")
    role_arn      = aws_iam_role.agentcore.arn
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      EXISTING=$(aws bedrock-agentcore-control list-agent-runtimes \
        --region ${var.aws_region} \
        --query "agentRuntimes[?agentRuntimeName=='${local.agentcore_runtime_name}'].agentRuntimeId" \
        --output text 2>/dev/null || echo "")

      if [ -z "$EXISTING" ]; then
        echo "Creating AgentCore runtime..."
        aws bedrock-agentcore-control create-agent-runtime \
          --region ${var.aws_region} \
          --agent-runtime-name ${local.agentcore_runtime_name} \
          --description "Daily AI newsletter pipeline" \
          --role-arn ${aws_iam_role.agentcore.arn} \
          --agent-runtime-artifact '{"codeConfiguration":{"runtime":"PYTHON_3_12","entryPoint":["agent.py"],"code":{"s3":{"bucket":"${aws_s3_bucket.agent_code.id}","prefix":"agent.zip"}}}}' \
          --network-configuration '{"networkMode":"PUBLIC"}' \
          --environment-variables '{"APP_REGION":"${var.aws_region}"}'
      else
        echo "Updating AgentCore runtime $EXISTING..."
        aws bedrock-agentcore-control update-agent-runtime \
          --region ${var.aws_region} \
          --agent-runtime-id $EXISTING \
          --role-arn ${aws_iam_role.agentcore.arn} \
          --agent-runtime-artifact '{"codeConfiguration":{"runtime":"PYTHON_3_12","entryPoint":["agent.py"],"code":{"s3":{"bucket":"${aws_s3_bucket.agent_code.id}","prefix":"agent.zip"}}}}' \
          --environment-variables '{"APP_REGION":"${var.aws_region}"}'
      fi
    EOT
  }

  depends_on = [aws_s3_object.agent_zip, aws_iam_role_policy.agentcore]
}

# ─── EventBridge — Lambda invoker triggers AgentCore runtime daily ────────────

resource "aws_cloudwatch_log_group" "invoker_lambda" {
  name              = "/aws/lambda/early-newsletter-invoker"
  retention_in_days = 180
}

data "archive_file" "invoker" {
  type        = "zip"
  source_file = "${path.module}/../agentcore/invoker.py"
  output_path = "${path.module}/../dist/invoker.zip"
}

resource "aws_lambda_function" "invoker" {
  function_name    = "early-newsletter-invoker"
  role             = aws_iam_role.lambda_exec.arn
  runtime          = "python3.12"
  handler          = "invoker.handler"
  filename         = data.archive_file.invoker.output_path
  source_code_hash = data.archive_file.invoker.output_base64sha256
  timeout          = 30
  memory_size      = 128

  environment {
    variables = {
      APP_REGION            = var.aws_region
      AGENTCORE_RUNTIME_NAME = local.agentcore_runtime_name
    }
  }

  tracing_config {
    mode = "Active"
  }

  depends_on = [aws_cloudwatch_log_group.invoker_lambda]
}

resource "aws_lambda_permission" "eventbridge_invoker" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.invoker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_pipeline.arn
}

resource "aws_cloudwatch_event_target" "invoker" {
  rule = aws_cloudwatch_event_rule.daily_pipeline.name
  arn  = aws_lambda_function.invoker.arn
}
