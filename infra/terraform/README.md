# Terraform (AWS)

このディレクトリは、以下を作成する最小構成です。
- ECR
- ECS Fargate (FastAPI)
- ECS Fargate (OCR worker)
- ALB
- RDS PostgreSQL
- S3 (uploads)
- SQS (OCR jobs)
- CloudWatch Logs
- IAM Role/Policy
- Secrets Manager (DATABASE_URL)

## 前提
- 既存VPCとサブネットを利用します（新規VPCは作りません）
- `terraform` と `aws` CLI が利用可能
- AWS認証情報が設定済み

## 事前確認
権限不足を先に洗い出す場合:
```bash
AWS_REGION=ap-northeast-1 ./scripts/aws-preflight.sh
```

最小権限の叩き台:
- [iam-minimum-policy.json](/Users/matsumototakahiro/order-automation-poc/infra/terraform/iam-minimum-policy.json)

## 使い方

1. 変数ファイルを作成
```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

2. `terraform.tfvars` の `vpc_id`, `subnet_ids` を実環境で更新

3. 適用
```bash
terraform init
terraform plan
terraform apply
```

4. ECRへイメージをpush
- `terraform output ecr_repository_url` の値に対して push

5. ECSを再デプロイ
- 新タグを使う場合は `image_tag` 変更または `container_image_override` を設定
- `terraform apply` で更新

## オンデマンド運用（推奨）
- `terraform.tfvars` の既定は `desired_count=0`, `worker_desired_count=0`（常時停止）です。
- 必要時にサービスを起動:
```bash
AWS_PROFILE=terraform-deployer AWS_REGION=ap-northeast-1 ../../scripts/aws-scale-services.sh up
```
- 稼働状態確認:
```bash
AWS_PROFILE=terraform-deployer AWS_REGION=ap-northeast-1 ../../scripts/aws-scale-services.sh status
```
- 利用後に停止:
```bash
AWS_PROFILE=terraform-deployer AWS_REGION=ap-northeast-1 ../../scripts/aws-scale-services.sh down
```

## 注意
- この構成は dev/staging 向けの最小テンプレートです。
- 本番では HTTPS(ACM), WAF, AutoScaling, バックアップ/削除保護強化を追加してください。
