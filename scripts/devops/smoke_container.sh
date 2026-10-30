#!/usr/bin/env bash
# Container smoke test for the runtime image.
#   1. start the image on a private network (ef-smoke-<id>)
#   2. wait until the Docker HEALTHCHECK reports "healthy" (timeout 60 s)
#   3. check /_stcore/health from a second container on the same network
#   4. render every page inside the container (scripts/devops/page_smoke.py)
#   5. assert the container runs as non-root and /app holds no .env file
# Only the resources created here (ef-smoke-<id>*) are removed on exit.
#
# Usage: scripts/devops/smoke_container.sh <image> [id]
set -euo pipefail

IMAGE="${1:?usage: $0 <image> [id]}"
ID="${2:-$$}"
NAME="ef-smoke-${ID}"
TIMEOUT="${SMOKE_TIMEOUT:-60}"

cleanup() {
    docker rm -f "${NAME}" >/dev/null 2>&1 || true
    docker network rm "${NAME}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker network create "${NAME}" >/dev/null
docker run -d --name "${NAME}" --network "${NAME}" "${IMAGE}" >/dev/null
echo "smoke: started ${NAME} from ${IMAGE}"

status=""
for _ in $(seq 1 "${TIMEOUT}"); do
    status="$(docker inspect -f '{{.State.Health.Status}}' "${NAME}")"
    [ "${status}" = "healthy" ] && break
    if [ "$(docker inspect -f '{{.State.Running}}' "${NAME}")" != "true" ]; then
        docker logs "${NAME}" | tail -n 50
        echo "smoke: FAIL container exited" >&2
        exit 1
    fi
    sleep 1
done
if [ "${status}" != "healthy" ]; then
    docker logs "${NAME}" | tail -n 50
    echo "smoke: FAIL not healthy after ${TIMEOUT}s (status=${status})" >&2
    exit 1
fi
echo "smoke: health status = ${status}"

body="$(docker run --rm --network "${NAME}" --entrypoint python "${IMAGE}" -c \
    "import urllib.request; print(urllib.request.urlopen('http://${NAME}:8501/_stcore/health', timeout=5).read().decode())")"
[ "${body}" = "ok" ] || { echo "smoke: FAIL health body '${body}'" >&2; exit 1; }
echo "smoke: GET http://${NAME}:8501/_stcore/health from a second container -> ${body}"

uid="$(docker exec "${NAME}" id -u)"
[ "${uid}" != "0" ] || { echo "smoke: FAIL container runs as root" >&2; exit 1; }
echo "smoke: container uid = ${uid} ($(docker exec "${NAME}" id -un))"

envs="$(docker exec "${NAME}" find /app -name '.env*' -o -name 'secrets.toml')"
[ -z "${envs}" ] || { echo "smoke: FAIL secret-like files in /app: ${envs}" >&2; exit 1; }
echo "smoke: no .env / secrets.toml under /app"

docker exec "${NAME}" python scripts/devops/page_smoke.py
echo "smoke: PASS"
