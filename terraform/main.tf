terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "dark-web-ai-newsletter"
      ManagedBy   = "terraform"
    }
  }
}

# ─── DynamoDB ────────────────────────────────────────────────────────────────

resource "aws_dynamodb_table" "config" {
  name         = "dark-web-newsletter-config"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "config_key"

  attribute {
    name = "config_key"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = { Name = "dark-web-newsletter-config" }
}

resource "aws_dynamodb_table" "run_history" {
  name         = "dark-web-newsletter-runs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "run_date"
  range_key    = "run_id"

  attribute {
    name = "run_date"
    type = "S"
  }

  attribute {
    name = "run_id"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }

  point_in_time_recovery {
    enabled = true
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = { Name = "dark-web-newsletter-runs" }
}

# ─── Secrets Manager ─────────────────────────────────────────────────────────

resource "aws_secretsmanager_secret" "credentials" {
  name                    = "dark-web-newsletter/credentials"
  description             = "API keys and OAuth tokens for the newsletter pipeline"
  recovery_window_in_days = 7

  tags = { Name = "dark-web-newsletter-credentials" }
}

resource "aws_secretsmanager_secret_version" "credentials_placeholder" {
  secret_id = aws_secretsmanager_secret.credentials.id
  secret_string = jsonencode({
    github_token          = "REPLACE_ME"
    reddit_client_id      = "REPLACE_ME"
    reddit_client_secret  = "REPLACE_ME"
    slack_token           = "REPLACE_ME"
    huggingface_token     = ""
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# ─── SES ─────────────────────────────────────────────────────────────────────

resource "aws_ses_email_identity" "sender" {
  email = var.email_sender
}

# ─── IAM — Lambda execution role ─────────────────────────────────────────────

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_exec" {
  name               = "dark-web-newsletter-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda_policy" {
  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:*:*:*"]
  }

  statement {
    sid    = "XRay"
    effect = "Allow"
    actions = [
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "DynamoDB"
    effect = "Allow"
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
    sid    = "SecretsManager"
    effect = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.credentials.arn]
  }

  statement {
    sid    = "SES"
    effect = "Allow"
    actions = ["ses:SendEmail", "ses:SendRawEmail"]
    resources = ["*"]
  }

  statement {
    sid    = "Bedrock"
    effect = "Allow"
    actions = ["bedrock:InvokeModel"]
    resources = ["*"]
  }

  statement {
    sid    = "CloudWatch"
    effect = "Allow"
    actions = ["cloudwatch:PutMetricData"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "lambda_policy" {
  name   = "dark-web-newsletter-lambda-policy"
  role   = aws_iam_role.lambda_exec.id
  policy = data.aws_iam_policy_document.lambda_policy.json
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
