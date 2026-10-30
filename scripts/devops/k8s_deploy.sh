#!/usr/bin/env bash
# Deploy an image to the k3d cluster "eduforecast": import, apply, wait, health check.
# Usage: scripts/devops/k8s_deploy.sh [image]     (default eduforecast:latest)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CLUSTER="eduforecast"
IMAGE="${1:-eduforecast:latest}"
export KUBECONFIG="${HOME}/.eduforecast-ci/kubeconfig"
[ -f "${KUBECONFIG}" ] || { echo "k8s_deploy: run scripts/devops/k3d_up.sh first" >&2; exit 1; }

k3d image import "${IMAGE}" --cluster "${CLUSTER}"
kubectl apply -f "${ROOT}/k8s/deployment.yaml" -f "${ROOT}/k8s/service.yaml"
kubectl set image deployment/eduforecast eduforecast="${IMAGE}"
kubectl rollout status deployment/eduforecast --timeout=180s

port=18501
kubectl port-forward service/eduforecast "${port}:8501" >/dev/null 2>&1 &
pf=$!
trap 'kill "${pf}" 2>/dev/null || true' EXIT
for _ in $(seq 1 20); do
    body="$(curl -fsS "http://127.0.0.1:${port}/_stcore/health" 2>/dev/null || true)"
    [ "${body}" = "ok" ] && break
    sleep 1
done
[ "${body:-}" = "ok" ] || { echo "k8s_deploy: FAIL health via port-forward" >&2; exit 1; }
echo "k8s_deploy: ${IMAGE} rolled out; /_stcore/health -> ${body}"
kubectl get deployment,pods,service -l app.kubernetes.io/name=eduforecast
