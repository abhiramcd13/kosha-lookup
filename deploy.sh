
#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID=${1:-}
if [[ -z "$PROJECT_ID" ]]; then
  echo "Usage: bash deploy.sh YOUR_PROJECT_ID"
  exit 1
fi
REGION="asia-south1"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/kosha/kosha-lookup:v2-2"
gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
gcloud artifacts repositories create kosha --repository-format=docker --location="$REGION" || true
gcloud builds submit --tag "$IMAGE"
gcloud run deploy kosha-lookup \
  --image "$IMAGE" \
  --region "$REGION" \
  --allow-unauthenticated \
  --min-instances=1 \
  --port=8080 \
  --timeout=600
