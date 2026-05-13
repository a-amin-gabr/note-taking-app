#!/bin/bash
# =============================================================
# Deploy Script — Package Lambda + Sync Static + Terraform Apply
# Usage: ./deploy.sh
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
APP_DIR="$ROOT_DIR/app"
TF_DIR="$ROOT_DIR/terraform"
PKG_DIR="$ROOT_DIR/package"
STATIC_SRC="$(dirname "$ROOT_DIR")/static"
TF_STATE_BUCKET="${TF_STATE_BUCKET:-notes-app-terraform-state}"
TF_STATE_KEY="${TF_STATE_KEY:-serverless/terraform.tfstate}"
TF_STATE_REGION="${TF_STATE_REGION:-${AWS_REGION:-eu-central-1}}"

echo "=== Step 1: Package Lambda ==="
rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR/build"

pip install -r "$APP_DIR/requirements.txt" -t "$PKG_DIR/build" --quiet

cp "$APP_DIR"/*.py "$PKG_DIR/build/"
cp -r "$APP_DIR/templates" "$PKG_DIR/build/"
mkdir -p "$PKG_DIR/build/static"
cp -r "$STATIC_SRC/images" "$PKG_DIR/build/static/"


cd "$PKG_DIR/build"
zip -r "$PKG_DIR/lambda.zip" . -q
echo "  → lambda.zip created ($(du -sh "$PKG_DIR/lambda.zip" | cut -f1))"

echo ""
echo "=== Step 2: Terraform Init + Apply ==="
cd "$TF_DIR"
terraform init \
	-backend-config="bucket=${TF_STATE_BUCKET}" \
	-backend-config="key=${TF_STATE_KEY}" \
	-backend-config="region=${TF_STATE_REGION}"
terraform apply -auto-approve

STATIC_BUCKET=$(terraform output -raw static_bucket)
CF_DIST_ID=$(terraform output -raw cloudfront_distribution_id)

echo ""
echo "=== Step 3: Sync Static Assets to S3 ==="
aws s3 sync "$STATIC_SRC" "s3://$STATIC_BUCKET/static/" --delete
echo "  → Static assets synced to s3://$STATIC_BUCKET/static/"

echo ""
echo "=== Step 4: Invalidate CloudFront Cache ==="
aws cloudfront create-invalidation --distribution-id "$CF_DIST_ID" --paths "/static/*" --no-cli-pager
echo "  → Cache invalidated"

echo ""
echo "=== Deployment Complete ==="
terraform output
