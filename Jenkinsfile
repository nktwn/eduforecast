// EduForecast-SIS CI/CD pipeline (declarative).
// Lint and unit tests run inside the Docker test image; the runtime image is built,
// smoke-tested, optionally pushed, and deployed to the local test container on main.
// The Docker daemon is the host's (socket mounted into the Jenkins controller), so
// workspace files reach containers only through `docker build` and `docker cp`.

pipeline {
    agent any

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
    }

    triggers {
        pollSCM('H/2 * * * *')
    }

    parameters {
        booleanParam(name: 'PUSH_IMAGE', defaultValue: false,
            description: 'Push the runtime image to REGISTRY_IMAGE')
        string(name: 'REGISTRY_IMAGE', defaultValue: 'localhost:5000/eduforecast',
            description: 'Target repository, e.g. docker.io/<user>/eduforecast or localhost:5000/eduforecast')
        booleanParam(name: 'DEPLOY_TEST', defaultValue: true,
            description: 'Deploy to the test container eduforecast-test (port 8502); main branch only')
    }

    environment {
        IMAGE_NAME = 'eduforecast'
        TEST_CONTAINER = 'eduforecast-test'
        TEST_NETWORK = 'eduforecast-test-net'
        TEST_PORT = '8502'
    }

    stages {
        stage('Checkout') {
            steps {
                script {
                    env.SHORT_SHA = sh(script: 'git rev-parse --short=8 HEAD', returnStdout: true).trim()
                    env.GIT_FULL_SHA = sh(script: 'git rev-parse HEAD', returnStdout: true).trim()
                    env.EF_ID = "${env.BRANCH_NAME ?: 'job'}-${env.BUILD_NUMBER}".toLowerCase().replaceAll('[^a-z0-9_.-]', '-')
                    env.TEST_IMAGE = "eduforecast-ci-test:${env.EF_ID}"
                    env.IS_MAIN = (env.BRANCH_NAME == 'main') ? 'true' : 'false'
                }
                sh '''#!/bin/bash
                    set -euo pipefail
                    echo "branch=${BRANCH_NAME:-n/a} commit=${GIT_FULL_SHA} short=${SHORT_SHA} build=${BUILD_NUMBER}"
                    git log -1 --format='author=%an date=%cI subject=%s'
                    docker version --format 'docker client {{.Client.Version}} / daemon {{.Server.Version}} ({{.Server.Arch}})'
                '''
            }
        }

        stage('Build test image') {
            steps {
                sh '''#!/bin/bash
                    set -euo pipefail
                    DOCKER_BUILDKIT=1 docker build --target test -t "${TEST_IMAGE}" .
                '''
            }
        }

        stage('Lint') {
            steps {
                // Same rule set as .github/workflows/ci.yml
                sh '''#!/bin/bash
                    set -euo pipefail
                    docker run --rm "${TEST_IMAGE}" ruff check --select E9,F63,F7,F82 app src tests
                '''
            }
        }

        stage('Unit tests') {
            steps {
                sh '''#!/bin/bash
                    set -euo pipefail
                    rm -rf reports && mkdir -p reports
                    name="ef-tests-${EF_ID}"
                    docker rm -f "${name}" >/dev/null 2>&1 || true
                    set +e
                    docker run --name "${name}" "${TEST_IMAGE}"
                    rc=$?
                    set -e
                    docker cp "${name}:/tmp/reports/." reports/ || echo "no reports produced"
                    docker rm "${name}" >/dev/null
                    echo "pytest exit code: ${rc}"
                    exit "${rc}"
                '''
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/junit.xml'
                    archiveArtifacts allowEmptyArchive: true, artifacts: 'reports/junit.xml,reports/coverage.xml'
                }
            }
        }

        stage('Build image') {
            steps {
                sh '''#!/bin/bash
                    set -euo pipefail
                    tags=(-t "${IMAGE_NAME}:${SHORT_SHA}" -t "${IMAGE_NAME}:build-${BUILD_NUMBER}")
                    if [ "${IS_MAIN}" = "true" ]; then tags+=(-t "${IMAGE_NAME}:latest"); fi
                    DOCKER_BUILDKIT=1 docker build --target runtime \
                        --build-arg GIT_SHA="${GIT_FULL_SHA}" \
                        --build-arg BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
                        "${tags[@]}" .
                    mkdir -p reports
                    {
                        echo "image=${IMAGE_NAME}:${SHORT_SHA}"
                        echo "tags=${IMAGE_NAME}:${SHORT_SHA} ${IMAGE_NAME}:build-${BUILD_NUMBER}$([ "${IS_MAIN}" = "true" ] && echo " ${IMAGE_NAME}:latest")"
                        docker image inspect "${IMAGE_NAME}:${SHORT_SHA}" --format 'id={{.Id}}
size_bytes={{.Size}}
arch={{.Architecture}}
user={{.Config.User}}
revision={{index .Config.Labels "org.opencontainers.image.revision"}}
created={{index .Config.Labels "org.opencontainers.image.created"}}'
                    } | tee reports/image-info.txt
                    docker run --rm --entrypoint pip "${IMAGE_NAME}:${SHORT_SHA}" freeze > reports/pip-freeze.txt
                    echo "pip freeze: $(wc -l < reports/pip-freeze.txt) packages"
                '''
                archiveArtifacts artifacts: 'reports/image-info.txt,reports/pip-freeze.txt'
            }
        }

        stage('Smoke test') {
            steps {
                sh '''#!/bin/bash
                    set -euo pipefail
                    bash scripts/devops/smoke_container.sh "${IMAGE_NAME}:${SHORT_SHA}" "${EF_ID}"
                '''
            }
        }

        stage('Push image') {
            when { expression { return params.PUSH_IMAGE } }
            steps {
                script {
                    def target = (params.REGISTRY_IMAGE ?: '').trim()
                    if (!target) {
                        error('PUSH_IMAGE is true but REGISTRY_IMAGE is empty')
                    }
                    env.PUSH_TARGET = target
                    def first = target.tokenize('/')[0]
                    def isLocal = first.startsWith('localhost:') || first.startsWith('127.0.0.1:')
                    def pushBody = '''
                        tags=("${SHORT_SHA}" "build-${BUILD_NUMBER}")
                        if [ "${IS_MAIN}" = "true" ]; then tags+=(latest); fi
                        for t in "${tags[@]}"; do
                            docker tag "${IMAGE_NAME}:${SHORT_SHA}" "${PUSH_TARGET}:${t}"
                            docker push --quiet "${PUSH_TARGET}:${t}"
                        done
                        docker image inspect "${PUSH_TARGET}:${SHORT_SHA}" --format 'pushed digests: {{json .RepoDigests}}'
                    '''
                    if (isLocal) {
                        sh('#!/bin/bash\nset -euo pipefail\n' + pushBody)
                    } else {
                        env.REGISTRY_HOST = (first.contains('.') || first.contains(':')) ? first : 'docker.io'
                        withCredentials([usernamePassword(credentialsId: 'dockerhub-credentials',
                                usernameVariable: 'REG_USER', passwordVariable: 'REG_TOKEN')]) {
                            // Isolated DOCKER_CONFIG: the token never lands in the shared host config.
                            sh '''#!/bin/bash
                                set -euo pipefail
                                export DOCKER_CONFIG="$(mktemp -d)"
                                trap 'docker logout "${REGISTRY_HOST}" >/dev/null 2>&1 || true; rm -rf "${DOCKER_CONFIG}"' EXIT
                                printf '%s' "${REG_TOKEN}" | docker login --username "${REG_USER}" --password-stdin "${REGISTRY_HOST}"
                            ''' + pushBody
                        }
                    }
                }
            }
        }

        stage('Deploy to test server') {
            when {
                allOf {
                    expression { return params.DEPLOY_TEST }
                    branch 'main'
                }
            }
            steps {
                sh '''#!/bin/bash
                    set -euo pipefail
                    image="${IMAGE_NAME}:${SHORT_SHA}"
                    docker network inspect "${TEST_NETWORK}" >/dev/null 2>&1 || docker network create "${TEST_NETWORK}" >/dev/null
                    previous="$(docker inspect -f '{{.Config.Image}}' "${TEST_CONTAINER}" 2>/dev/null)" || previous="none"
                    docker rm -f "${TEST_CONTAINER}" >/dev/null 2>&1 || true
                    docker run -d --name "${TEST_CONTAINER}" --network "${TEST_NETWORK}" \
                        --restart unless-stopped -p "127.0.0.1:${TEST_PORT}:8501" \
                        --label "eduforecast.build=${BUILD_NUMBER}" --label "eduforecast.revision=${GIT_FULL_SHA}" \
                        "${image}" >/dev/null
                    status=""
                    for _ in $(seq 1 90); do
                        status="$(docker inspect -f '{{.State.Health.Status}}' "${TEST_CONTAINER}")"
                        [ "${status}" = "healthy" ] && break
                        sleep 1
                    done
                    [ "${status}" = "healthy" ] || { docker logs "${TEST_CONTAINER}" | tail -n 50; echo "deploy: not healthy (${status})"; exit 1; }
                    body="$(docker run --rm --network "${TEST_NETWORK}" --entrypoint python "${image}" -c \
                        "import urllib.request; print(urllib.request.urlopen('http://${TEST_CONTAINER}:8501/_stcore/health', timeout=5).read().decode())")"
                    [ "${body}" = "ok" ] || { echo "deploy: health body '${body}'"; exit 1; }
                    echo "deploy: ${previous} -> ${image} (status ${status}, health ${body})"
                    echo "deploy: test server URL http://localhost:${TEST_PORT}"
                '''
            }
        }
    }

    post {
        always {
            sh '''#!/bin/bash
                set -uo pipefail
                for c in "ef-tests-${EF_ID:-none}" "ef-smoke-${EF_ID:-none}"; do
                    docker rm -f "${c}" >/dev/null 2>&1 || true
                done
                docker network rm "ef-smoke-${EF_ID:-none}" >/dev/null 2>&1 || true
                docker image rm "${TEST_IMAGE:-eduforecast-ci-test:none}" >/dev/null 2>&1 || true
                echo "cleanup: removed temporary ef-* resources of ${EF_ID:-n/a}"
            '''
            cleanWs()
        }
        failure {
            echo 'Pipeline failed. Open the first red stage: Lint -> ruff output; Unit tests -> "Test Result" page and reports/junit.xml; Build image / Smoke test -> docker build or container logs above.'
        }
        success {
            echo "Pipeline passed: ${env.IMAGE_NAME}:${env.SHORT_SHA}"
        }
    }
}
