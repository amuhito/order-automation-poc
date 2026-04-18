# AWS deployment guide (ECS Fargate + RDS + S3 + SQS)

## 1. Architecture
- Runtime: ECS Fargate (FastAPI container)
- OCR worker: ECS Fargate (queue consumer)
- Database: RDS PostgreSQL
- File storage: S3
- Queue: SQS
- Entry: ALB + ACM + Route53
- Logs: CloudWatch Logs

## 2. Build and push image
```bash
docker build -t order-automation-poc:latest .
```

Push to ECR (example):
```bash
aws ecr get-login-password --region ap-northeast-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com
docker tag order-automation-poc:latest <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com/order-automation-poc:latest
docker push <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com/order-automation-poc:latest
```

## 3. Required environment variables
Set these in ECS task definition:
- `DATABASE_URL=postgresql+psycopg://<user>:<password>@<rds-endpoint>:5432/<db>`
- `STORAGE_BACKEND=s3`
- `S3_BUCKET=<bucket-name>`
- `S3_PREFIX=order-automation/uploads`
- `AWS_REGION=ap-northeast-1`
- `OCR_ASYNC_ENABLED=true`
- `OCR_QUEUE_BACKEND=sqs`
- `OCR_QUEUE_URL=<sqs-queue-url>`
- `S3_PUBLIC_BASE_URL=<optional-cloudfront-url>`

Store DB password and secrets in Secrets Manager, then inject to task.

## 4. IAM permissions for task role
Minimum S3 permissions:
- `s3:PutObject`
- `s3:GetObject`
- `s3:ListBucket`

Scope to target bucket/prefix.

Minimum SQS permissions (task role):
- `sqs:SendMessage`
- `sqs:ReceiveMessage`
- `sqs:DeleteMessage`
- `sqs:ChangeMessageVisibility`
- `sqs:GetQueueAttributes`

## 5. Database initialization
The app runs schema creation at startup (`init_db()`), including missing-column backfill for legacy records.

## 6. ALB health check
Use path:
- `/kanban`

Expected code:
- `200`

## 7. Operational notes
- OCR uses Tesseract in the app container; keep task CPU/memory with OCR load in mind.
- Presigned URL mode is used for S3 unless `S3_PUBLIC_BASE_URL` is set.
- For multi-instance production, keep all uploads in S3 and do not rely on local `uploads/`.
- Cost-optimized dev operation: keep ECS desired count at 0 and scale up only when needed using `scripts/aws-scale-services.sh`.
