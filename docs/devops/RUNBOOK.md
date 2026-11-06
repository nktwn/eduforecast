# Runbook

All commands from the repository root on the host (macOS, Docker Desktop).

## 1. Images without Jenkins

```bash
make docker-test          # test image, pytest; reports/junit.xml, reports/coverage.xml
make docker-lint          # ruff, same rules as CI
make docker-build         # runtime image eduforecast:dev
make smoke                # container smoke test of eduforecast:dev
make docker-run           # app on http://localhost:8501 (Ctrl+C stops it)
```

## 2. Jenkins

```bash
make jenkins-env          # creates jenkins/.env.jenkins (git-ignored, mode 600) with a random admin password
make mirror-sync BRANCHES="main"     # local mirror ~/.eduforecast-ci/eduforecast.git (needed before first start)
make jenkins-up           # build + start, http://localhost:8080 (about 30 s to healthy; first build of the image ~9 min)
make jenkins-down         # stop; the jenkins_home volume eduforecast_jenkins_home is kept
```

- **Credentials:** user `admin`, password in `jenkins/.env.jenkins` (`JENKINS_ADMIN_PASSWORD`). Read it with an editor; it is never printed by the scripts.
- **No setup wizard:** all configuration comes from `jenkins/casc/jenkins.yaml` (JCasC); the job `eduforecast` is created by Job DSL at start-up.
- **Changing configuration:** edit `jenkins/casc/*.yaml` or `jenkins/plugins.txt`, then `make jenkins-up` (rebuild + recreate).
- **Reset Jenkins completely:** `docker compose -f jenkins/docker-compose.yml down -v` (deletes build history).

### Repository source

`GIT_REPO_URL` in `jenkins/.env.jenkins`:

| value | when |
|---|---|
| `https://github.com/nktwn/eduforecast.git` | default (public repo, no credentials needed) |
| `file:///mirror/eduforecast.git` | only to validate commits that are not pushed yet; update with `scripts/devops/sync_mirror.sh` (`src:dst` maps a local branch to a mirror branch, e.g. `devops/docker-jenkins:main`) |

After changing it: `docker compose -f jenkins/docker-compose.yml up -d --force-recreate jenkins`, then **Scan Multibranch Pipeline Now** on the job (or wait 2 minutes).

### Running with parameters

Job `eduforecast` → branch → **Build with Parameters**: `PUSH_IMAGE`, `REGISTRY_IMAGE`, `DEPLOY_TEST`.
The first build of a new branch uses the defaults (`PUSH_IMAGE=false`, `DEPLOY_TEST=true`).

## 3. Registry push

### Local registry (validated)

```bash
make registry-up                     # eduforecast-registry on 127.0.0.1:5000
# Build with Parameters: PUSH_IMAGE=true, REGISTRY_IMAGE=localhost:5000/eduforecast
curl -s http://127.0.0.1:5000/v2/_catalog
curl -s http://127.0.0.1:5000/v2/eduforecast/tags/list
make registry-down
```

### Docker Hub (documented, not executed)

1. Docker Hub → Account settings → Personal access tokens → **Generate new token** (Read & Write).
2. In `jenkins/.env.jenkins` set `DOCKERHUB_USERNAME=<user>` and `DOCKERHUB_TOKEN=<token>`.
3. `docker compose -f jenkins/docker-compose.yml up -d --force-recreate jenkins` — the entrypoint enables `casc/optional/dockerhub.yaml`, which creates the credential `dockerhub-credentials` (log line `ef-entrypoint: Docker Hub credentials enabled`).
4. Build with Parameters: `PUSH_IMAGE=true`, `REGISTRY_IMAGE=docker.io/<user>/eduforecast`.

The pipeline logs in with `--password-stdin` into a temporary `DOCKER_CONFIG` and logs out afterwards; Jenkins masks the token in the console.

### Multi-arch images (recipe, not executed)

The host is arm64, so local builds produce `linux/arm64`. For an amd64 + arm64 image on Docker Hub:

```bash
docker buildx create --name eduforecast-multi --use
docker buildx build --platform linux/amd64,linux/arm64 --target runtime \
  --build-arg GIT_SHA=$(git rev-parse HEAD) -t docker.io/<user>/eduforecast:<tag> --push .
docker buildx rm eduforecast-multi
```

The amd64 half runs under QEMU emulation and is several times slower.

## 4. Test server

The pipeline deploys `eduforecast-test` on http://localhost:8502 (main branch).

```bash
curl -s http://localhost:8502/_stcore/health          # ok
docker inspect -f '{{.Config.Image}}' eduforecast-test
docker rm -f eduforecast-test && docker network rm eduforecast-test-net   # stop it
```

## 5. Optional Kubernetes (k3d) — not executed

Requires `brew install k3d` (owner consent). About 0.5–0.8 GB of Docker VM memory.

```bash
make k8s-up               # cluster "eduforecast", private kubeconfig ~/.eduforecast-ci/kubeconfig
make k8s-deploy TAG=latest
make k8s-down
```

The scripts never use the default kubeconfig, so the stale `minikube` context is untouched.

## 6. Troubleshooting

| symptom | cause / fix |
|---|---|
| Jenkins unhealthy, log `UnknownAttributesException ... excludeClientIPFromCrumb` | removed attribute in this Jenkins version; the crumb issuer block is now omitted (default CSRF protection) |
| Checkout fails `unable to open loose object ... Permission denied` on `file:///mirror/...` | objects in the mirror were hard-linked from a `git clone` of the mirror; Docker Desktop file sharing could not read them. Clone the mirror with `git clone --no-local` |
| Build job HTTP 400 from `/build` | the job is parameterized; use `/buildWithParameters` |
| `tests/test_advisor_facts.py` fails with `FileNotFoundError: 'git'` in the test image | git missing in slim image; the test stage installs it |
| one commit built twice on main | happened while the Jenkinsfile also had `pollSCM`; removed, only the 2-minute branch scan triggers builds now. The first build after the change can still be doubled because the old trigger is stored in the job until a build with the new Jenkinsfile runs |
| `docker: permission denied` inside Jenkins | the container must run as root (compose `user: root`) to use the mounted socket |
| Jenkins killed / slow | `mem_limit: 1536m`, heap `-Xmx768m`; Docker VM has 3.8 GiB, stop other stacks if needed |

## 7. Resources and security notes

- Docker VM memory 3.8 GiB: Jenkins idles at ~770 MiB, the test container ~130 MiB, registry ~30 MiB; builds run one at a time (`numExecutors: 1`, `disableConcurrentBuilds`).
- Disk: runtime image 1.64 GB as listed by `docker images` (layers shared between tags), Jenkins image 1.08 GB, jenkins_home ~280 MB. Old tags: `docker image rm eduforecast:<tag>`; never use unfiltered `docker system prune`.
- Mounting `/var/run/docker.sock` gives Jenkins root-equivalent control of the Docker host; acceptable only locally. Jenkins listens on 127.0.0.1:8080, no anonymous read, no agent port.
- Secrets: `.env`, `jenkins/.env.jenkins`, `.streamlit/secrets.toml` are git-ignored and excluded from the build context. Run `make prepush-audit` before pushing.
