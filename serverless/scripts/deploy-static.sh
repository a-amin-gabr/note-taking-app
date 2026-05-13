#!/bin/bash
# =============================================================
# Sync Static Assets to S3
# Usage: ./deploy-static.sh
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TF_DIR="$(dirname "$SCRIPT_DIR")/terraform"
STATIC_SRC="$(dirname "$(dirname "$SCRIPT_DIR")")/static"

cd "$TF_DIR"
STATIC_BUCKET=$(terraform output -raw static_bucket)
CF_DIST_ID=$(terraform output -raw cloudfront_distribution_id)

echo "Syncing static assets to s3://$STATIC_BUCKET/static/ ..."
aws s3 sync "$STATIC_SRC" "s3://$STATIC_BUCKET/static/" --delete

echo "Invalidating CloudFront cache..."
aws cloudfront create-invalidation --distribution-id "$CF_DIST_ID" --paths "/static/*" --no-cli-pager

echo "Done!"
