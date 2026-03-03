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
          metrics = [["DarkWebAINewsletter", "PipelineDuration"]]
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
            ["DarkWebAINewsletter", "ItemsScraped", "Source", "arxiv"],
            ["DarkWebAINewsletter", "ItemsScraped", "Source", "github"],
            ["DarkWebAINewsletter", "ItemsScraped", "Source", "huggingface"],
            ["DarkWebAINewsletter", "ItemsScraped", "Source", "reddit"],
            ["DarkWebAINewsletter", "ItemsScraped", "Source", "aws_changelog"],
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
            ["DarkWebAINewsletter", "ItemsAfterFilter"],
            ["DarkWebAINewsletter", "ItemsInDigest"],
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
            ["DarkWebAINewsletter", "DeliverySuccess", "Channel", "slack"],
            ["DarkWebAINewsletter", "DeliverySuccess", "Channel", "email"],
            ["DarkWebAINewsletter", "DeliveryFailure", "Channel", "slack"],
            ["DarkWebAINewsletter", "DeliveryFailure", "Channel", "email"],
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
            ["AWS/Lambda", "Errors", "FunctionName", "dark-web-newsletter-health"],
            ["AWS/Lambda", "Duration", "FunctionName", "dark-web-newsletter-health"],
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
          query  = "SOURCE '/aws/lambda/dark-web-newsletter-health' | fields @timestamp, error_message, agent_name | filter level = 'ERROR' | sort @timestamp desc | limit 20"
          view   = "table"
        }
      },
    ]
  })
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "dark-web-ai-newsletter"
  dashboard_body = local.dashboard_body
}
