#!/usr/bin/env bash
set -euo pipefail

BUCKET="netskope-events"
echo "🪣 creating S3 bucket: $BUCKET"

# awslocal は LocalStack イメージに同梱済み
awslocal s3 mb "s3://$BUCKET" || true
