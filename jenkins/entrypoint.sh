#!/bin/bash
# Assemble the active JCasC directory, then start Jenkins.
# casc/optional/dockerhub.yaml is enabled only when both Docker Hub variables are set,
# so no empty credential is created otherwise.
set -euo pipefail

conf="${CASC_JENKINS_CONFIG:-/var/jenkins_conf}"
mkdir -p "${conf}"
rm -f "${conf}"/*.yaml
cp /usr/share/jenkins/casc/jenkins.yaml "${conf}/"
if [ -n "${DOCKERHUB_USERNAME:-}" ] && [ -n "${DOCKERHUB_TOKEN:-}" ]; then
    cp /usr/share/jenkins/casc/optional/dockerhub.yaml "${conf}/"
    echo "ef-entrypoint: Docker Hub credentials enabled (dockerhub-credentials)"
fi

exec /usr/local/bin/jenkins.sh "$@"
