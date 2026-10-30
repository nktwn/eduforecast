# Jenkins controller for EduForecast CI: LTS + JDK 21, Docker CLI/buildx, plugins and
# Configuration as Code. No setup wizard; everything comes from casc/ and plugins.txt.
ARG JENKINS_IMAGE=jenkins/jenkins:2.580.2-lts-jdk21
FROM ${JENKINS_IMAGE}

USER root

# Docker CLI + buildx from the official Docker apt repository (for this image's arch).
# The daemon is the host's, reached through the mounted /var/run/docker.sock.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-buildx-plugin \
    && rm -rf /var/lib/apt/lists/*

# The local mirror (file:///mirror/...) is owned by the host user; allow git to use it.
RUN git config --system --add safe.directory '*'

USER jenkins
COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

# Configuration last, so editing it does not re-download plugins.
COPY casc/ /usr/share/jenkins/casc/
COPY --chmod=0755 entrypoint.sh /usr/local/bin/ef-entrypoint.sh

ENV CASC_JENKINS_CONFIG=/var/jenkins_conf
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/ef-entrypoint.sh"]
