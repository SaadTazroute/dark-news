locals {
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 8
        height = 6
        properties = {
          title  = "Pipeline Duration (seconds)"
          region = var.aws_region
          metrics = [["EarlyAINewsletter", "PipelineDuration"]]
          view   = "timeSeries"
          stat   = "Average"
          period = 86400
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 0
        width  = 8
        height = 6
        properties = {
          title  = "Items Scraped per Source"
          region = var.aws_region
          metrics = [
            ["EarlyAINewsletter", "ItemsScraped", "Source", "arxiv"],
            ["EarlyAINewsletter", "ItemsScraped", "Source", "github"],
            ["EarlyAINewsletter", "ItemsScraped", "Source", "huggingface"],
            ["EarlyAINewsletter", "ItemsScraped", "Source", "reddit"],
            ["EarlyAINewsletter", "ItemsScraped", "Source", "aws_changelog"],
          ]
          view   = "timeSeries"
          stat   = "Sum"
          period = 86400
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 0
        width  = 8
        height = 6
        properties = {
          title  = "Items After Filter & In Digest"
          region = var.aws_region
          metrics = [
            ["EarlyAINewsletter", "ItemsAfterFilter"],
            ["EarlyAINewsletter", "ItemsInDigest"],
          ]
          view   = "timeSeries"
          stat   = "Sum"
          period = 86400
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 8
        height = 6
        properties = {
          title  = "Delivery Success / Failure"
          region = var.aws_region
          metrics = [
            ["EarlyAINewsletter", "DeliverySuccess", "Channel", "slack"],
            ["EarlyAINewsletter", "DeliverySuccess", "Channel", "email"],
            ["EarlyAINewsletter", "DeliveryFailure", "Channel", "slack"],
            ["EarlyAINewsletter", "DeliveryFailure", "Channel", "email"],
          ]
          view   = "timeSeries"
          stat   = "Sum"
          period = 86400
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 6
        width  = 8
        height = 6
        properties = {
          title  = "Lambda /health — Errors & Duration"
          region = var.aws_region
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", "early-newsletter-health"],
            ["AWS/Lambda", "Duration", "FunctionName", "early-newsletter-health"],
          ]
          view   = "timeSeries"
          stat   = "Sum"
          period = 3600
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 6
        width  = 8
        height = 6
        properties = {
          title  = "Bedrock Invocation Errors"
          region = var.aws_region
          metrics = [
            ["AWS/Bedrock", "InvocationClientErrors"],
            ["AWS/Bedrock", "InvocationServerErrors"],
          ]
          view   = "timeSeries"
          stat   = "Sum"
          period = 86400
        }
      },
      {
        type   = "log"
        x      = 0
        y      = 12
        width  = 24
        height = 6
        properties = {
          title  = "Last Failing Pipeline Requests"
          region = var.aws_region
          query  = "SOURCE '/aws/lambda/early-newsletter-health' | fields @timestamp, error_message, agent_name | filter level = 'ERROR' | sort @timestamp desc | limit 20"
          view   = "table"
        }
      },
    ]
  })
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "early-ai-newsletter"
  dashboard_body = local.dashboard_body
}
