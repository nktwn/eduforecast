#!/usr/bin/env bash
# Delete the k3d cluster "eduforecast" and its private kubeconfig. Nothing else is touched.
set -euo pipefail

k3d cluster delete eduforecast
rm -f "${HOME}/.eduforecast-ci/kubeconfig"
echo "k3d_down: cluster eduforecast deleted"
