"""
setup_secrets.py - CLI tool to push studio secrets to Google Cloud Secret Manager

Usage:
  python setup_secrets.py --project YOUR_GCP_PROJECT [--env-file .env]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

STUDIO_KEYS = [
    "GEMINI_API_KEY",
    "CONFLUENT_BOOTSTRAP_SERVERS",
    "CONFLUENT_API_KEY",
    "CONFLUENT_API_SECRET",
    "CONFLUENT_TOPIC",
]


def push_secrets(project_id: str, env_path: Path):
    try:
        from google.cloud import secretmanager
    except ImportError:
        print("ERROR: Please install google-cloud-secret-manager:")
        print("  pip install google-cloud-secret-manager")
        sys.exit(1)

    if not env_path.exists():
        print(f"ERROR: Env file not found at {env_path}")
        sys.exit(1)

    vals = dotenv_values(env_path)
    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project_id}"

    print(f"=== Pushing Studio Secrets to Secret Manager ===")
    print(f"Target Project: {project_id}\n")

    pushed_count = 0
    for key in STUDIO_KEYS:
        val = vals.get(key) or os.getenv(key)
        if not val:
            print(f"  [-] {key}: Not present in {env_path.name}, skipping.")
            continue

        secret_id = key.replace("_", "-").lower()

        # 1. Create secret if it doesn't exist
        try:
            client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_id,
                    "secret": {"replication": {"automatic": {}}},
                }
            )
            print(f"  [+] Created secret '{secret_id}'")
        except Exception:
            # Already exists
            pass

        # 2. Add secret version
        try:
            client.add_secret_version(
                request={
                    "parent": f"{parent}/secrets/{secret_id}",
                    "payload": {"data": str(val).encode("utf-8")},
                }
            )
            print(f"  [✓] Updated secret version for '{secret_id}'")
            pushed_count += 1
        except Exception as e:
            print(f"  [!] Failed to add version for '{secret_id}': {e}")

    print(f"\nCompleted: {pushed_count} secret(s) stored securely in Google Cloud Secret Manager.")


def main():
    parser = argparse.ArgumentParser(description="Upload studio secrets to Google Cloud Secret Manager")
    parser.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT", ""), help="Google Cloud Project ID")
    parser.add_argument("--env-file", default=".env", help="Path to .env file containing secrets")
    args = parser.parse_args()

    if not args.project:
        print("ERROR: Missing --project. Please pass --project YOUR_PROJECT_ID or set GOOGLE_CLOUD_PROJECT.")
        sys.exit(1)

    env_path = Path(args.env_file)
    if not env_path.is_absolute():
        env_path = Path(__file__).parent / args.env_file

    push_secrets(args.project, env_path)


if __name__ == "__main__":
    main()
