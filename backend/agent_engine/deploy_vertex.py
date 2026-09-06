"""
deploy_vertex.py - Vertex AI Agent Engine Deployment Script

Deploys the Flawless Take ContinuitySupervisorAgent to Google Cloud Vertex AI
Reasoning Engine / Agent Engine managed serverless runtime.

Prerequisites:
  1. gcloud auth application-default login
  2. pip install "google-cloud-aiplatform>=1.57.0"
  3. GCS staging bucket created in the target region.

Usage:
  python deploy_vertex.py \
    --project YOUR_PROJECT_ID \
    --location us-central1 \
    --staging-bucket gs://your-staging-bucket \
    --display-name "flawless-take-continuity-agent"
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_CURRENT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _CURRENT_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


def deploy(
    project: str,
    location: str,
    staging_bucket: str,
    display_name: str,
    model: str,
) -> None:
    print(f"=== Deploying Flawless Take to Vertex AI Agent Engine ===")
    print(f"Project:        {project}")
    print(f"Location:       {location}")
    print(f"Staging Bucket: {staging_bucket}")
    print(f"Display Name:   {display_name}")
    print(f"Model:          {model}\n")

    try:
        import vertexai
        from vertexai.preview import reasoning_engines
    except ImportError:
        print(
            "ERROR: 'google-cloud-aiplatform' is required for Vertex AI deployment.\n"
            "Install it via:\n"
            "  pip install 'google-cloud-aiplatform>=1.57.0'",
            file=sys.stderr,
        )
        sys.exit(1)

    # Initialize Vertex AI SDK
    vertexai.init(
        project=project,
        location=location,
        staging_bucket=staging_bucket,
    )

    from agent_engine.agent import ContinuitySupervisorAgent

    # Instantiate local agent template
    agent = ContinuitySupervisorAgent(
        model=model,
        project=project,
        location=location,
    )

    requirements = [
        "google-genai>=0.5.0",
        "pydantic>=2.7.0",
        "aiosqlite>=0.20.0",
        "reportlab>=4.2.0",
        "fastmcp>=2.0.0",
        "confluent-kafka>=2.4.0",
    ]

    print("Uploading agent and packaging dependencies to Vertex AI...")
    try:
        remote_agent = reasoning_engines.ReasoningEngine.create(
            agent,
            requirements=requirements,
            extra_packages=[str(_BACKEND_DIR)],
            display_name=display_name,
            description="Flawless Take Autonomous AI Continuity Supervisor (Film & TV)",
        )
        print("\n=== Deployment Succeeded! ===")
        print(f"Resource Name: {remote_agent.resource_name}")
        print("\nYou can now query the deployed agent via Python:")
        print(f"""
from vertexai.preview import reasoning_engines
remote = reasoning_engines.ReasoningEngine("{remote_agent.resource_name}")
result = remote.query(prompt="Check continuity drift for Scene 14A", scene="Scene 14A")
print(result)
""")
    except Exception as exc:
        print(f"\nERROR: Vertex AI deployment failed: {exc}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Deploy Flawless Take to Vertex AI Agent Engine"
    )
    parser.add_argument(
        "--project",
        default=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        help="Google Cloud Project ID",
    )
    parser.add_argument(
        "--location",
        default=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        help="Vertex AI region (default: us-central1)",
    )
    parser.add_argument(
        "--staging-bucket",
        default=os.getenv("VERTEX_STAGING_BUCKET", ""),
        help="GCS staging bucket (e.g. gs://my-bucket)",
    )
    parser.add_argument(
        "--display-name",
        default="flawless-take-continuity-supervisor",
        help="Agent display name in Vertex AI console",
    )
    parser.add_argument(
        "--model",
        default="gemini-3.8-flash",
        help="Gemini foundation model",
    )
    args = parser.parse_args()

    if not args.project:
        print(
            "ERROR: Missing --project. Please pass --project or set GOOGLE_CLOUD_PROJECT.",
            file=sys.stderr,
        )
        sys.exit(1)
    if not args.staging_bucket:
        print(
            "ERROR: Missing --staging-bucket. Please pass --staging-bucket or set VERTEX_STAGING_BUCKET.",
            file=sys.stderr,
        )
        sys.exit(1)

    deploy(
        project=args.project,
        location=args.location,
        staging_bucket=args.staging_bucket,
        display_name=args.display_name,
        model=args.model,
    )


if __name__ == "__main__":
    main()
