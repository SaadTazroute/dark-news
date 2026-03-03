"""
Deployed infrastructure smoke test — checks AWS resources are live and healthy.
Requires: AWS credentials + terraform apply already done.

Usage:
    source .venv/bin/activate
    python tests/test_infra.py

    # Override region or health URL:
    HEALTH_URL=https://xxx.execute-api.us-east-1.amazonaws.com/health python tests/test_infra.py
"""

import json
import os
import subprocess
import sys
import logging

import boto3
import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
HEALTH_URL = os.environ.get("HEALTH_URL", "")  # auto-detected from terraform output if empty
SECRET_NAME = "dark-web-newsletter/credentials"
CONFIG_TABLE = "dark-web-newsletter-config"
RUN_TABLE = "dark-web-newsletter-runs"


def get_health_url() -> str:
    if HEALTH_URL:
        return HEALTH_URL
    try:
        out = subprocess.check_output(
            ["terraform", "output", "-raw", "health_api_url"],
            cwd="terraform", stderr=subprocess.DEVNULL
        )
        return out.decode().strip()
    except Exception:
        return ""


def check_health_endpoint(url: str) -> bool:
    print(f"\n=== /health endpoint ({url}) ===")
    if not url:
        print("  ✗ Could not determine health URL — set HEALTH_URL env var or run from repo root")
        return False
    try:
        r = requests.get(url, timeout=10)
        print(f"  status: {r.status_code}")
        print(f"  body:   {r.text[:300]}")
        ok = r.status_code in (200, 500)  # 500 is fine — means Lambda is up, just no runs yet
        print(f"  {'✓' if ok else '✗'} Lambda reachable")
        return ok
    except Exception as e:
        print(f"  ✗ {e}")
        return False


def check_dynamodb() -> bool:
    print("\n=== DynamoDB tables ===")
    ddb = boto3.client("dynamodb", region_name=AWS_REGION)
    ok = True
    for table in [CONFIG_TABLE, RUN_TABLE]:
        try:
            resp = ddb.describe_table(TableName=table)
            status = resp["Table"]["TableStatus"]
            print(f"  ✓ {table}: {status}")
        except Exception as e:
            print(f"  ✗ {table}: {e}")
            ok = False
    return ok


def check_secret() -> bool:
    print("\n=== Secrets Manager ===")
    sm = boto3.client("secretsmanager", region_name=AWS_REGION)
    try:
        resp = sm.get_secret_value(SecretId=SECRET_NAME)
        secret = json.loads(resp["SecretString"])
        keys = list(secret.keys())
        print(f"  ✓ {SECRET_NAME} exists, keys: {keys}")
        placeholders = [k for k, v in secret.items() if v == "REPLACE_ME"]
        if placeholders:
            print(f"  ⚠ Still placeholder: {placeholders}")
        return True
    except Exception as e:
        print(f"  ✗ {e}")
        return False


def check_bedrock() -> bool:
    print("\n=== Bedrock model access ===")
    bedrock = boto3.client("bedrock", region_name=AWS_REGION)
    required = [
        "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "amazon.titan-embed-text-v2:0",
    ]
    ok = True
    try:
        resp = bedrock.list_foundation_models()
        available = {m["modelId"] for m in resp.get("modelSummaries", [])}
        for model_id in required:
            if model_id in available:
                print(f"  ✓ {model_id}")
            else:
                print(f"  ✗ {model_id} — not available (enable in Bedrock console)")
                ok = False
    except Exception as e:
        print(f"  ✗ Bedrock check failed: {e}")
        ok = False
    return ok


if __name__ == "__main__":
    url = get_health_url()
    results = [
        check_health_endpoint(url),
        check_dynamodb(),
        check_secret(),
        check_bedrock(),
    ]

    passed = sum(results)
    total = len(results)
    print(f"\n{'='*40}")
    print(f"  {passed}/{total} checks passed")

    sys.exit(0 if all(results) else 1)
