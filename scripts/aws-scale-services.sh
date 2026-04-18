#!/usr/bin/env bash

set -euo pipefail

ACTION="${1:-}"
if [[ -z "${ACTION}" ]]; then
  echo "Usage: $0 <up|down|status>"
  exit 1
fi

AWS_PROFILE="${AWS_PROFILE:-default}"
AWS_REGION="${AWS_REGION:-ap-northeast-1}"
TF_DIR="${TF_DIR:-infra/terraform}"

CLUSTER="$(AWS_PROFILE="${AWS_PROFILE}" terraform -chdir="${TF_DIR}" output -raw ecs_cluster_name)"
APP_SVC="$(AWS_PROFILE="${AWS_PROFILE}" terraform -chdir="${TF_DIR}" output -raw ecs_service_name)"
WORKER_SVC="$(AWS_PROFILE="${AWS_PROFILE}" terraform -chdir="${TF_DIR}" output -raw ecs_worker_service_name)"

show_status() {
  aws ecs describe-services \
    --cluster "${CLUSTER}" \
    --services "${APP_SVC}" "${WORKER_SVC}" \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}" \
    --query 'services[].{name:serviceName,running:runningCount,desired:desiredCount,status:status}' \
    --output table
}

case "${ACTION}" in
  up)
    aws ecs update-service --cluster "${CLUSTER}" --service "${APP_SVC}" --desired-count 1 --profile "${AWS_PROFILE}" --region "${AWS_REGION}" >/dev/null
    aws ecs update-service --cluster "${CLUSTER}" --service "${WORKER_SVC}" --desired-count 1 --profile "${AWS_PROFILE}" --region "${AWS_REGION}" >/dev/null
    echo "Scaled up app/worker to 1."
    show_status
    ;;
  down)
    aws ecs update-service --cluster "${CLUSTER}" --service "${WORKER_SVC}" --desired-count 0 --profile "${AWS_PROFILE}" --region "${AWS_REGION}" >/dev/null
    aws ecs update-service --cluster "${CLUSTER}" --service "${APP_SVC}" --desired-count 0 --profile "${AWS_PROFILE}" --region "${AWS_REGION}" >/dev/null
    echo "Scaled down app/worker to 0."
    show_status
    ;;
  status)
    show_status
    ;;
  *)
    echo "Unknown action: ${ACTION}"
    echo "Usage: $0 <up|down|status>"
    exit 1
    ;;
esac
