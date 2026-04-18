#!/usr/bin/env bash

set -euo pipefail

REGION="${AWS_REGION:-ap-northeast-1}"

run_check() {
  local label="$1"
  shift

  if output="$("$@" 2>&1)"; then
    printf "[OK]   %s\n" "$label"
  else
    printf "[FAIL] %s\n" "$label"
    printf "       %s\n" "$output" | tr '\n' ' '
    printf "\n"
  fi
}

echo "AWS preflight checks for region: ${REGION}"
echo

run_check "STS identity" \
  aws sts get-caller-identity --region "${REGION}" --output json

run_check "EC2 describe VPCs" \
  aws ec2 describe-vpcs --region "${REGION}" --max-items 5 --output json

run_check "EC2 describe subnets" \
  aws ec2 describe-subnets --region "${REGION}" --max-items 5 --output json

run_check "ECR describe repositories" \
  aws ecr describe-repositories --region "${REGION}" --max-items 5 --output json

run_check "ECS list clusters" \
  aws ecs list-clusters --region "${REGION}" --max-items 5 --output json

run_check "RDS describe DB instances" \
  aws rds describe-db-instances --region "${REGION}" --max-records 20 --output json

run_check "S3 list buckets" \
  aws s3api list-buckets --region "${REGION}" --output json

run_check "ELBv2 describe load balancers" \
  aws elbv2 describe-load-balancers --region "${REGION}" --page-size 5 --output json

run_check "Secrets Manager list secrets" \
  aws secretsmanager list-secrets --region "${REGION}" --max-results 5 --output json
