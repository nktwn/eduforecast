#!/usr/bin/env bash
# Create or update a LOCAL bare mirror that Jenkins can read before anything is pushed
# to GitHub. Force-push is used ONLY towards this mirror path, never towards origin.
#
# Usage: scripts/devops/sync_mirror.sh [branch | local:mirror-branch ...]
#        default: main and the current branch. Example before the branch is merged:
#        scripts/devops/sync_mirror.sh devops/docker-jenkins:main   (repo's main is untouched)
# Mirror: ${EF_MIRROR:-$HOME/.eduforecast-ci/eduforecast.git}  (mounted in Jenkins as /mirror)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MIRROR="${EF_MIRROR:-${HOME}/.eduforecast-ci/eduforecast.git}"

case "${MIRROR}" in
    "${HOME}"/.eduforecast-ci/*) ;;
    *) echo "sync_mirror: refusing mirror path outside ~/.eduforecast-ci: ${MIRROR}" >&2; exit 1 ;;
esac

if [ "$#" -gt 0 ]; then
    branches=("$@")
else
    current="$(git -C "${ROOT}" branch --show-current)"
    branches=(main)
    [ -n "${current}" ] && [ "${current}" != "main" ] && branches+=("${current}")
fi

if [ ! -d "${MIRROR}" ]; then
    mkdir -p "$(dirname "${MIRROR}")"
    git init --bare --quiet --initial-branch=main "${MIRROR}"
    echo "sync_mirror: created ${MIRROR}"
fi

for spec in "${branches[@]}"; do
    src="${spec%%:*}"
    dst="${spec#*:}"
    git -C "${ROOT}" push --quiet --force "${MIRROR}" "refs/heads/${src}:refs/heads/${dst}"
    echo "sync_mirror: ${src} -> mirror ${dst} @ $(git -C "${MIRROR}" rev-parse --short "refs/heads/${dst}")"
done
