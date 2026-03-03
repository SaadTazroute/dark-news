# Dark Web AI Newsletter

> **48 hours ahead of the curve** — an agentic platform that surfaces high-signal AI and cloud intelligence before mainstream newsletters cover it.

## Executive Summary

This platform monitors obscure, day-0 sources (arxiv preprints, GitHub commit activity, HuggingFace model uploads, Reddit comment velocity, AWS changelog RSS) and delivers a daily curated digest to Slack and Gmail. It uses a multi-agent pipeline built on the Strands Agents SDK, deployed serverlessly on AWS via AgentCore. The result: you read about new research, model releases, and infrastructure changes 48 hours before they appear in any newsletter.

---

## TL;DR

```bash
# 1. Set up Python environment
uv venv .venv && uv pip install -r requirements.txt

# 2. Deploy infrastructure
cd terraform
terraform init
terraform apply -var="email_sender=chris.moltisanti667@egmail.com" -var="email_recipient=chris.moltisanti667@example.com"

# 3. Populate secrets (replace REPLACE_ME values)
aws secretsmanager put-secret-value \
  --secret-id dark-web-newsletter/credentials \
  --secret-string '{"github_token":"ghp_...","reddit_client_id":"...","reddit_client_secret":"...","slack_token":"xoxb-..."}'

# 4. Deploy the orchestrator to AgentCore (see AgentCore deployment guide)
# 5. The pipeline runs daily at 06:00 UTC — check Slack + email
```

---

## Architecture

```
EventBridge (daily cron)
    └── OrchestratorAgent (AgentCore)
            ├── ArxivAgent          → cs.AI, cs.LG, cs.AR preprints
            ├── GitHubSignalAgent   → commits on key AI repos
            ├── HuggingFaceAgent    → new model uploads
            ├── RedditAgent         → posts by comment velocity
            └── AWSChangelogAgent   → raw AWS changelog RSS
                    │
                    ▼
            RelevanceFilter (Bedrock Titan Embeddings)
            — deduplication + ranking
                    │
                    ▼
            SummarizerAgent (Claude 3.5 Sonnet)
            — nerd-tone, consultant-angle digest
                    │
                    ▼
            PublisherAgent
            ├── Slack (Block Kit)
            └── Gmail (SES HTML email)
```

---

## Project Structure

```
src/
  orchestrator.py       # Pipeline coordinator
  models.py             # SignalItem, Digest, PipelineResult
  config.py             # Loads secrets + DynamoDB config
  relevance_filter.py   # Bedrock embeddings, dedup, ranking
  summarizer.py         # Claude summarization + Jinja rendering
  metrics.py            # CloudWatch metrics emitter
  retry.py              # Shared retry decorator
  registry.py           # Scraper + publisher plugin registries
  logging_utils.py      # Structured JSON logging
  scrapers/             # One file per source (self-registering)
  publishers/           # One file per channel (self-registering)
templates/
  digest_plain.j2       # Slack plain-text template
  digest_html.j2        # Email HTML template
terraform/              # All AWS infrastructure
health/
  handler.py            # Lambda /health endpoint
```

---

## Setup

### Prerequisites

- Python 3.11+ with [uv](https://docs.astral.sh/uv/)
- Terraform >= 1.5
- AWS CLI configured with appropriate permissions
- AWS account with Bedrock model access enabled (Claude 3.5 Sonnet + Titan Embeddings)

### Python environment

```bash
uv venv .venv
uv pip install -r requirements.txt
```

### Infrastructure deployment

```bash
cd terraform
terraform init
terraform apply \
  -var="email_sender=digest@yourdomain.com" \
  -var="email_recipient=you@yourdomain.com" \
  -var="slack_channel=#ai-digest"
```

### Populate credentials

After `terraform apply`, update the Secrets Manager secret with real values:

| Key | Description |
|-----|-------------|
| `github_token` | GitHub Personal Access Token (read:repo scope) |
| `reddit_client_id` | Reddit app client ID |
| `reddit_client_secret` | Reddit app client secret |
| `slack_token` | Slack Bot Token (`xoxb-...`) |
| `huggingface_token` | HuggingFace token (optional, for private models) |

```bash
aws secretsmanager put-secret-value \
  --secret-id dark-web-newsletter/credentials \
  --secret-string '{"github_token":"ghp_...","reddit_client_id":"...","reddit_client_secret":"...","slack_token":"xoxb-..."}'
```

### Non-sensitive config (DynamoDB)

Optional overrides stored in the `dark-web-newsletter-config` DynamoDB table:

| config_key | Default | Description |
|------------|---------|-------------|
| `arxiv_categories` | `["cs.AI","cs.LG","cs.AR"]` | Arxiv categories to monitor |
| `github_repos` | 5 default repos | List of repos to watch |
| `reddit_subreddits` | `["MachineLearning","LocalLLaMA","aws"]` | Subreddits to monitor |
| `reddit_velocity_threshold` | `1.0` | Min comments/hour to include a post |
| `similarity_threshold` | `0.85` | Cosine similarity dedup threshold |
| `max_items` | `30` | Max items in the digest |

---

## Adding a New Source

1. Create `src/scrapers/your_source.py`
2. Implement the `ScraperAgent` interface and decorate with `@register_scraper("your_source")`
3. Add `from src.scrapers import your_source  # noqa: F401` to `src/scrapers/__init__.py`

That's it — the orchestrator picks it up automatically.

## Adding a New Delivery Channel

1. Create `src/publishers/your_channel.py`
2. Implement the `PublisherChannel` interface and decorate with `@register_publisher("your_channel")`
3. Add `from src.publishers import your_channel  # noqa: F401` to `src/publishers/__init__.py`

---

## Observability

- **Logs**: CloudWatch Logs at `/aws/lambda/dark-web-newsletter-health` (180-day retention)
- **Metrics**: Custom namespace `DarkWebAINewsletter` — pipeline duration, items per source, delivery success/failure
- **Dashboard**: `dark-web-ai-newsletter` CloudWatch Dashboard (URL in Terraform outputs)
- **Health**: `GET /health` returns last pipeline run status, item counts, and any errors
- **Tracing**: AWS X-Ray active tracing on all Lambda functions

---

## Troubleshooting

**No digest received**: Check the CloudWatch Dashboard for scraper failures. Verify credentials in Secrets Manager.

**Slack not posting**: Confirm `slack_token` is a Bot Token (`xoxb-`) and the bot is invited to the channel.

**SES email not arriving**: Verify the sender address is confirmed in SES. Check SES sending limits.

**Bedrock errors**: Ensure the AWS account has model access enabled for `anthropic.claude-3-5-sonnet-20241022-v2:0` and `amazon.titan-embed-text-v1` in the target region.
