#!/usr/bin/env bash
# Create jenkins/.env.jenkins (git-ignored) with a random admin password.
# The password is never printed; read it from the file when you need to log in.
# Usage: scripts/devops/jenkins_env.sh [git-repo-url]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${ROOT}/jenkins/.env.jenkins"
REPO_URL="${1:-file:///mirror/eduforecast.git}"

if [ -f "${ENV_FILE}" ]; then
    echo "jenkins_env: ${ENV_FILE} already exists, left unchanged"
    exit 0
fi

umask 077
{
    echo "JENKINS_ADMIN_ID=admin"
    echo "JENKINS_ADMIN_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-24)"
    echo "GIT_REPO_URL=${REPO_URL}"
    echo "DOCKERHUB_USERNAME="
    echo "DOCKERHUB_TOKEN="
} > "${ENV_FILE}"
echo "jenkins_env: wrote ${ENV_FILE} (mode 600; admin password not shown)"
