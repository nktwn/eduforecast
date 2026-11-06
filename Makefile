# DevOps shortcuts for EduForecast-SIS (GNU Make 3.81 compatible). See docs/devops/RUNBOOK.md.
IMAGE        ?= eduforecast
TAG          ?= dev
TEST_IMAGE   ?= eduforecast-ci-test:$(TAG)
GIT_SHA      := $(shell git rev-parse HEAD 2>/dev/null || echo unknown)
BUILD_DATE   := $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
COMPOSE      := docker compose -f jenkins/docker-compose.yml
RUN_PORT     ?= 8501

.PHONY: help docker-build docker-test docker-lint docker-run smoke jenkins-env jenkins-up \
        jenkins-down jenkins-logs registry-up registry-down mirror-sync prepush-audit \
        k8s-up k8s-deploy k8s-down

help:
	@echo "docker-build   build the runtime image $(IMAGE):$(TAG)"
	@echo "docker-test    build the test image and run pytest (reports in ./reports)"
	@echo "docker-lint    ruff (same rules as CI) inside the test image"
	@echo "docker-run     run the runtime image on http://localhost:$(RUN_PORT)"
	@echo "smoke          container smoke test of $(IMAGE):$(TAG)"
	@echo "jenkins-env    create jenkins/.env.jenkins with a random admin password"
	@echo "jenkins-up     build and start Jenkins on http://localhost:8080"
	@echo "jenkins-down   stop Jenkins (jenkins_home volume is kept)"
	@echo "registry-up    start the local registry on localhost:5000"
	@echo "mirror-sync    update the local bare mirror Jenkins reads (BRANCHES=...)"
	@echo "prepush-audit  secret and data scan before pushing to GitHub"
	@echo "k8s-up / k8s-deploy / k8s-down   optional k3d cluster 'eduforecast'"

docker-build:
	docker build --target runtime --build-arg GIT_SHA=$(GIT_SHA) --build-arg BUILD_DATE=$(BUILD_DATE) \
		-t $(IMAGE):$(TAG) .

docker-test:
	docker build --target test -t $(TEST_IMAGE) .
	rm -rf reports && mkdir -p reports
	docker rm -f ef-tests-make >/dev/null 2>&1 || true
	docker run --name ef-tests-make $(TEST_IMAGE); rc=$$?; \
		docker cp ef-tests-make:/tmp/reports/. reports/; docker rm ef-tests-make >/dev/null; exit $$rc

docker-lint:
	docker build --target test -t $(TEST_IMAGE) .
	docker run --rm $(TEST_IMAGE) ruff check --select E9,F63,F7,F82 app src tests

docker-run:
	docker run --rm -p 127.0.0.1:$(RUN_PORT):8501 --name ef-run-make $(IMAGE):$(TAG)

smoke:
	scripts/devops/smoke_container.sh $(IMAGE):$(TAG) make

jenkins-env:
	scripts/devops/jenkins_env.sh

jenkins-up: jenkins-env
	mkdir -p $(HOME)/.eduforecast-ci
	$(COMPOSE) up -d --build

jenkins-down:
	$(COMPOSE) down

jenkins-logs:
	docker logs --tail 100 -f eduforecast-jenkins

registry-up:
	$(COMPOSE) --profile testreg up -d registry

registry-down:
	$(COMPOSE) --profile testreg rm -sf registry

mirror-sync:
	scripts/devops/sync_mirror.sh $(BRANCHES)

prepush-audit:
	scripts/devops/prepush_audit.sh

k8s-up:
	scripts/devops/k3d_up.sh

k8s-deploy:
	scripts/devops/k8s_deploy.sh $(IMAGE):$(TAG)

k8s-down:
	scripts/devops/k3d_down.sh
