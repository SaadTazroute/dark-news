"""AgentCore entrypoint — wraps OrchestratorAgent for Bedrock AgentCore Runtime."""

import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from src.orchestrator import OrchestratorAgent

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()
AWS_REGION = os.environ.get("APP_REGION", "eu-west-1")


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Run the full newsletter pipeline and return a summary."""
    logger.info(f"Pipeline triggered with payload: {payload}")
    region = payload.get("aws_region", AWS_REGION)
    result = OrchestratorAgent().run_pipeline(aws_region=region)
    return {
        "run_id": result.run_id,
        "items_scraped": result.items_scraped,
        "items_in_digest": result.items_in_digest,
        "error": result.error,
        "status": "failed" if result.error else "success",
    }


if __name__ == "__main__":
    app.run()
