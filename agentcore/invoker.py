"""Lambda invoker — triggered by EventBridge to invoke the AgentCore runtime."""

import json
import logging
import os
import uuid

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

REGION = os.environ["APP_REGION"]
RUNTIME_NAME = os.environ["AGENTCORE_RUNTIME_NAME"]


def _get_runtime_arn(control_client, name: str) -> str:
    resp = control_client.list_agent_runtimes()
    for rt in resp.get("agentRuntimes", []):
        if rt["agentRuntimeName"] == name:
            return rt["agentRuntimeArn"]
    raise ValueError(f"AgentCore runtime '{name}' not found")


def handler(event, context):
    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    runtime_arn = _get_runtime_arn(control, RUNTIME_NAME)

    client = boto3.client("bedrock-agentcore", region_name=REGION)
    session_id = str(uuid.uuid4())
    payload = json.dumps({"aws_region": REGION}).encode()

    logger.info(f"Invoking AgentCore runtime {runtime_arn}")
    client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        runtimeSessionId=session_id,
        payload=payload,
    )
    logger.info(f"Pipeline triggered, session={session_id}")
    return {"status": "triggered", "session_id": session_id}
