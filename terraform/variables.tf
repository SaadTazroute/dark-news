variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-west-1"
}

variable "schedule_expression" {
  description = "EventBridge cron/rate expression for the daily pipeline (e.g. 'cron(0 6 * * ? *)')"
  type        = string
  default     = "cron(0 6 * * ? *)"
}

variable "email_sender" {
  description = "Verified SES sender email address"
  type        = string
  default     = "chris.moltisanti667@gmail.com"
}

variable "email_recipient" {
  description = "Recipient email address for the digest"
  type        = string
  default     = "chris.moltisanti667@gmail.com"
}

variable "slack_channel" {
  description = "Slack channel to post the digest to (e.g. '#ai-digest')"
  type        = string
  default     = "#ai-digest"
}

variable "similarity_threshold" {
  description = "Cosine similarity threshold for deduplication (0.0–1.0)"
  type        = number
  default     = 0.85
}

variable "max_items" {
  description = "Maximum number of items to include in the digest"
  type        = number
  default     = 30
}


