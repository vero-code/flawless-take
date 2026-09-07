#!/usr/bin/env bash
# ==============================================================================
# deploy_cloud_run.sh - One-command deployment of Flawless Take to Google Cloud Run
# ==============================================================================
set -euo pipefail

PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-}}"
REGION="${2:-us-central1}"
SERVICE_NAME="flawless-take"

if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: Please specify your Google Cloud Project ID."
  echo "Usage: ./deploy_cloud_run.sh YOUR_PROJECT_ID [REGION]"
  exit 1
fi

echo "======================================================="
echo " Deploying Flawless Take to Google Cloud Run"
echo " Project: $PROJECT_ID"
echo " Region:  $REGION"
echo " Service: $SERVICE_NAME"
echo "======================================================="

IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

echo "Step 1: Building container with Google Cloud Build..."
gcloud builds submit --project "$PROJECT_ID" --tag "$IMAGE_NAME" .

echo "Step 2: Deploying to Google Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --project "$PROJECT_ID" \
  --image "$IMAGE_NAME" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"

echo "======================================================="
echo " Deployment Complete!"
echo " Getting Service URL..."
gcloud run services describe "$SERVICE_NAME" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --format='value(status.url)'
echo "======================================================="
