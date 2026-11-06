#!/usr/bin/env bash
# Create the local k3d cluster "eduforecast" (one server, no agents, no load balancer).
# Requires k3d on the host (brew install k3d) and roughly 0.5-0.8 GB of Docker VM memory.
# Only this cluster and its kubeconfig context (k3d-eduforecast) are touched.
set -euo pipefail

CLUSTER="eduforecast"
command -v k3d >/dev/null || { echo "k3d_up: k3d is not installed (brew install k3d)" >&2; exit 1; }

mem="$(docker info --format '{{.MemTotal}}')"
echo "k3d_up: Docker VM memory $((mem / 1024 / 1024)) MiB"

if k3d cluster list "${CLUSTER}" >/dev/null 2>&1; then
    echo "k3d_up: cluster ${CLUSTER} already exists"
else
    k3d cluster create "${CLUSTER}" --servers 1 --agents 0 --no-lb \
        --k3s-arg "--disable=traefik@server:0" --kubeconfig-update-default=false --wait
fi
mkdir -p "${HOME}/.eduforecast-ci"
k3d kubeconfig get "${CLUSTER}" > "${HOME}/.eduforecast-ci/kubeconfig"
chmod 600 "${HOME}/.eduforecast-ci/kubeconfig"
echo "k3d_up: kubeconfig at ~/.eduforecast-ci/kubeconfig (default kubeconfig untouched)"
KUBECONFIG="${HOME}/.eduforecast-ci/kubeconfig" kubectl get nodes
