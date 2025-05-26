# Netskope Event Collector

A robust, production-ready AWS Lambda application that collects security events from Netskope's Data Export API and stores them in Amazon S3 for analysis and long-term retention.

## Highlights

* Iterator-based Netskope API integration with pagination and rate limiting
* Gzip-compressed JSONL output to Amazon S3 using multipart upload
* CRC32 integrity checks with base64-encoded checksums
* Modular, typed Python codebase with complete unit and E2E testing
* LocalStack + mock API for full local testing without real credentials
* Deployable as a container-based Lambda function or ECS task

---

## Quick Start

```bash
# Start local dev environment (LocalStack + Mock API)
docker-compose -f .devcontainer/docker-compose.dev.yml up -d

# Run E2E test
python scripts/run_and_inspect.py

# Run unit tests
pytest
```

---

## Configuration

| Variable                     | Default                      | Description                        |
| ---------------------------- | ---------------------------- | ---------------------------------- |
| `NETSKOPE_API_ENDPOINT`      | `https://tenant.goskope.com` | API base URL                       |
| `NETSKOPE_TOKEN`             | *(required)*                 | API bearer token                   |
| `S3_BUCKET`                  | *(required)*                 | Target bucket name                 |
| `S3_PREFIX`                  | `raw/`                       | Output key prefix                  |
| `AWS_REGION`                 | `ap-northeast-1`             | AWS region                         |
| `S3_ENDPOINT`                | *(optional)*                 | Custom endpoint (e.g., LocalStack) |
| `FETCH_WINDOW_MINUTES`       | `15`                         | Time window                        |
| `MAX_FETCH_PAGES`            | `100`                        | Page cap                           |
| `MAX_FETCH_DURATION_SECONDS` | `300`                        | Duration cap                       |

---

## Endpoints Supported

* `application`
* `network`
* `page`
* `alert`
* `audit`

Custom paths can be configured via `NETSKOPE_ENDPOINTS`:

```bash
export NETSKOPE_ENDPOINTS='{"application": "/custom/path"}'
```

---

## Developer Notes

* `tests/test_units.py`: covers pagination, rate limit handling, and upload logic
* `src/netskope_collector/netskope_client.py`: typed HTTP client for iterator API
* `src/netskope_collector/s3_writer.py`: multipart gzip writer with CRC32
* `scripts/run_and_inspect.py`: end-to-end smoke test using mocked dependencies

---

## Test Coverage

```bash
pytest --cov --cov-report=term-missing
```

---

## Deployment (Lambda Container Image)

```bash
# Build and push to ECR
docker build -t netskope-collector .
docker tag netskope-collector $ECR_REPO:latest
docker push $ECR_REPO:latest

# Create function
aws lambda create-function \
  --function-name netskope-collector \
  --package-type Image \
  --code ImageUri=$ECR_REPO:latest \
  --role arn:aws:iam::123456789012:role/lambda-execution-role \
  --timeout 300 \
  --memory-size 512
```
