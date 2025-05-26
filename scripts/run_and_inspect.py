#!/usr/bin/env python3
"""
ECS 化後でもローカル E2E テストを 1 コマンドで行うスクリプト。
LocalStack & Netskope モックが docker-compose で立ち上がっている前提。
"""

import os
import sys
import gzip
import boto3
from io import BytesIO

# ----------------------------------------
# 環境変数 / 設定
# ----------------------------------------
os.environ.setdefault("AWS_ACCESS_KEY_ID", "dummy")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "dummy")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

ENDPOINT_URL = "http://localstack:4566"
BUCKET_NAME = "netskope-events"
ENDPOINT = os.getenv("ENDPOINT", "alert")
MINUTES_BACK = int(os.getenv("SINCE_MINUTES", "15"))

# ----------------------------------------
# Collector を直接実行
# ----------------------------------------
sys.path.insert(0, "src")
from netskope_collector.runner import run  # noqa: E402

s3_key = run(endpoint=ENDPOINT, since_minutes=MINUTES_BACK)
print(f"\n✅ Runner returned s3_key={s3_key}\n")

# ----------------------------------------
# S3 から結果を取得して表示
# ----------------------------------------
s3 = boto3.client("s3", endpoint_url=ENDPOINT_URL)

print(f"📦 Downloading s3://{BUCKET_NAME}/{s3_key} ...\n")
obj = s3.get_object(Bucket=BUCKET_NAME, Key=s3_key)
body = obj["Body"].read()

with gzip.GzipFile(fileobj=BytesIO(body)) as f:
    content = f.read().decode("utf-8")
    print("📄 File Content:")
    print(content)
