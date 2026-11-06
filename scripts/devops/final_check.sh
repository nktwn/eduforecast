#!/usr/bin/env bash
# Final read-only check of the Assignment 5 Definition of Done (D1-D12).
# Prints one PASS / FAIL / N/A line per check. Nothing is built, pushed or started.
#   GitHub: public REST API without a token (60 requests/hour) and a shallow clone into a temp dir.
#   Jenkins: GET only, credentials read from jenkins/.env.jenkins (never printed).
#   Docker: inspect / exec of read-only commands only.
# Usage: scripts/devops/final_check.sh
#   env: PR=<number of the DevOps pull request> (default: looked up by head branch)
#        RED_SHA=<commit of the deliberately failing test> (default: read from docs/devops/EVIDENCE.md)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "${ROOT}"
REPO="nktwn/eduforecast"
API="https://api.github.com/repos/${REPO}"
JENKINS="http://127.0.0.1:8080"
JOB="${JENKINS}/job/eduforecast"
HEAD_BRANCH="devops/docker-jenkins"
fails=0

line() { printf '%-4s %-5s %s\n' "$1" "$2" "$3"; [ "$2" = "FAIL" ] && fails=$((fails + 1)); return 0; }
gh_code() { curl -s -o /dev/null -w '%{http_code}' --max-time 20 "${API}$1"; }
gh_json() { curl -s --max-time 20 "${API}$1"; }

# Jenkins credentials: read into variables, never echoed; passed to curl via stdin config.
JUSER="$(grep '^JENKINS_ADMIN_ID=' jenkins/.env.jenkins 2>/dev/null | cut -d= -f2-)"
JPASS="$(grep '^JENKINS_ADMIN_PASSWORD=' jenkins/.env.jenkins 2>/dev/null | cut -d= -f2-)"
jget() { printf 'user = "%s:%s"\n' "${JUSER}" "${JPASS}" | curl -sg --max-time 20 -K - "$1"; }

echo "final_check $(date '+%Y-%m-%d %H:%M:%S %z')"

# D1 key files on public main
miss=""
for f in Jenkinsfile Dockerfile .dockerignore jenkins scripts/devops docs/devops docs/devops/README.md; do
    [ "$(gh_code "/contents/${f}?ref=main")" = "200" ] || miss="${miss} ${f}"
done
[ -z "${miss}" ] && line D1 PASS "GitHub main has Jenkinsfile, Dockerfile, .dockerignore, jenkins/, scripts/devops/, docs/devops/ (HTTP 200)" \
                 || line D1 FAIL "missing on GitHub main:${miss}"

# D2 PR merged with a merge commit
pr="${PR:-$(gh_json "/pulls?state=closed&head=nktwn:${HEAD_BRANCH}" | jq -r '[.[] | select(.merged_at != null)][0].number // empty')}"
if [ -n "${pr}" ]; then
    pj="$(gh_json "/pulls/${pr}")"
    merged="$(jq -r '.merged' <<<"${pj}")"; msha="$(jq -r '.merge_commit_sha' <<<"${pj}")"
    parents="$(gh_json "/commits/${msha}" | jq '.parents | length')"
    [ "${merged}" = "true" ] && [ "${parents}" = "2" ] \
        && line D2 PASS "PR #${pr} merged, merge commit ${msha:0:8} has 2 parents" \
        || line D2 FAIL "PR #${pr}: merged=${merged}, parents=${parents}"
else
    line D2 FAIL "no merged PR from ${HEAD_BRANCH}"
fi

# Jenkins reachability and job source (D5)
code="$(printf 'user = "%s:%s"\n' "${JUSER}" "${JPASS}" | curl -s -o /dev/null -w '%{http_code}' --max-time 10 -K - "${JENKINS}/api/json")"
anon="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "${JENKINS}/api/json")"
bind="$(docker port eduforecast-jenkins 8080/tcp 2>/dev/null | head -1)"
src="$(jget "${JOB}/config.xml" | grep -oE '<remote>[^<]+</remote>' | head -1 | sed 's/<[^>]*>//g')"
if [ "${code}" = "200" ] && [ "${anon}" = "403" ] && [ "${bind}" = "127.0.0.1:8080" ] && [ "${src}" = "https://github.com/${REPO}.git" ]; then
    line D5 PASS "Jenkins ${bind} (login 200, anonymous ${anon}), job source ${src}"
else
    line D5 FAIL "login=${code} anonymous=${anon} bind=${bind:-none} source=${src:-?}"
fi

# D3 GitHub-sourced green builds of the PR branch and main
enc_head="$(printf '%s' "${HEAD_BRANCH}" | sed 's|/|%252F|g')"
pr_res="$(jget "${JOB}/job/${enc_head}/lastBuild/api/json" | jq -r ".result // \"none\"" 2>/dev/null || echo none)"
main_res="$(jget "${JOB}/job/main/lastBuild/api/json" | jq -r '.result // "none"')"
main_remote="$(jget "${JOB}/job/main/lastBuild/api/json?tree=actions[remoteUrls]" | jq -r '[.actions[]?.remoteUrls[]?][0] // ""')"
[ "${pr_res}" = "SUCCESS" ] && [ "${main_res}" = "SUCCESS" ] && [ "${main_remote}" = "https://github.com/${REPO}.git" ] \
    && line D3 PASS "last ${HEAD_BRANCH} build SUCCESS, last main build SUCCESS from ${main_remote}" \
    || line D3 FAIL "branch=${pr_res} main=${main_res} remote=${main_remote:-?}"

# D6 stages of the last successful main build + test counts
mb="$(jget "${JOB}/job/main/lastSuccessfulBuild/api/json" | jq -r '.number // empty')"
stages="$(jget "${JOB}/job/main/${mb}/wfapi/describe" | jq -r '[.stages[] | select(.status=="SUCCESS") | .name] | join(",")')"
tests="$(jget "${JOB}/job/main/${mb}/testReport/api/json?tree=passCount,failCount,skipCount" | jq -r '"\(.passCount)/\(.failCount)/\(.skipCount)"')"
ok=1; for s in Checkout "Build test image" Lint "Unit tests" "Build image" "Smoke test" "Deploy to test server"; do
    grep -q "${s}" <<<"${stages}" || ok=0; done
[ "${ok}" = 1 ] && [ "${tests%%/*}" -gt 0 ] 2>/dev/null && [ "$(cut -d/ -f2 <<<"${tests}")" = "0" ] \
    && line D6 PASS "main #${mb}: all 7 stages SUCCESS; tests passed/failed/skipped ${tests}" \
    || line D6 FAIL "main #${mb:-?}: stages=[${stages}] tests=${tests}"

# D7 one build per commit, started automatically
builds="$(jget "${JOB}/job/main/api/json?tree=builds[number,result,actions[causes[shortDescription],parameters[name,value],lastBuiltRevision[SHA1],remoteUrls]]")"
# automatic = not started by a user (manual re-runs with parameters are not trigger duplicates)
auto="$(jq -r --arg u "https://github.com/${REPO}.git" '.builds[] | select([.actions[]?.remoteUrls[]?] | index($u))
        | select(([.actions[]?.causes[]?.shortDescription] | join(" ")) | test("user") | not)
        | "\(.number) \([.actions[]?.lastBuiltRevision.SHA1 // empty][0]) \([.actions[]?.causes[]?.shortDescription][0])"' <<<"${builds}")"
dups="$(awk '{print $2}' <<<"${auto}" | sort | uniq -d | grep -c . || true)"
newest="$(head -1 <<<"${auto}")"
[ -n "${auto}" ] && [ "${dups}" = "0" ] \
    && line D7 PASS "automatic GitHub-sourced main builds: $(grep -c . <<<"${auto}"), commits built twice: 0; newest: #${newest%% *} (${newest##* })" \
    || line D7 FAIL "automatic builds=$(grep -c . <<<"${auto}"), commits built twice=${dups}"

# D8 negative proof (captured log) + throwaway branch gone + failing commit not on main
red_log="$(ls docs/devops/ci-logs/github-ci-failure-demo-*.txt 2>/dev/null | tail -1)"
red_sha="${RED_SHA:-$(grep -oE 'red commit: [0-9a-f]{40}' docs/devops/EVIDENCE.md 2>/dev/null | head -1 | awk '{print $3}')}"
gone="$(gh_code "/branches/ci-failure-demo")"
cmp="$( [ -n "${red_sha}" ] && gh_json "/compare/${red_sha}...main" | jq -r '.status // "?"' )"
if [ -n "${red_log}" ] && grep -q 'Stage "Build image" skipped due to earlier failure' "${red_log}" \
   && grep -q 'Finished: FAILURE' "${red_log}" && [ "${gone}" = "404" ] && { [ "${cmp}" = "diverged" ] || [ "${cmp}" = "behind" ]; }; then
    line D8 PASS "$(basename "${red_log}"): FAILURE at Unit tests, Build image skipped; branch deleted (404); red commit ${red_sha:0:8} not on main (${cmp})"
else
    line D8 FAIL "log=${red_log:-none} branch=${gone} red_sha=${red_sha:-?} compare=${cmp:-?}"
fi

# D9 CD: test container runs the image of the last main build, health ok
health="$(curl -s --max-time 5 http://127.0.0.1:8502/_stcore/health)"
img="$(docker inspect -f '{{.Config.Image}}' eduforecast-test 2>/dev/null)"
crev="$(docker inspect -f '{{index .Config.Labels "eduforecast.revision"}}' eduforecast-test 2>/dev/null)"
msha="$(jq -r '.builds[0] | [.actions[]?.lastBuiltRevision.SHA1 // empty][0]' <<<"${builds}")"
[ "${health}" = "ok" ] && [ -n "${crev}" ] && [ "${crev}" = "${msha}" ] \
    && line D9 PASS "eduforecast-test runs ${img} (revision ${crev:0:8} = last main build), health ${health}" \
    || line D9 FAIL "health=${health:-none} image=${img:-none} container rev=${crev:0:8} main rev=${msha:0:8}"

# D10 registry push (local) and Docker Hub (only if configured)
tags="$(curl -s --max-time 5 http://127.0.0.1:5000/v2/eduforecast/tags/list | jq -r '.tags // [] | join(",")')"
hub="no"; grep -q '^DOCKERHUB_USERNAME=.' jenkins/.env.jenkins && grep -q '^DOCKERHUB_TOKEN=.' jenkins/.env.jenkins && hub="yes"
push="$(jq -r --arg u "https://github.com/${REPO}.git" '[.builds[] | select(.result=="SUCCESS") | select([.actions[]?.remoteUrls[]?] | index($u))
        | select([.actions[]?.parameters[]? | select(.name=="PUSH_IMAGE" and .value==true)] | length > 0)][0]
        | "\(.number) \([.actions[]?.lastBuiltRevision.SHA1 // empty][0])"' <<<"${builds}")"
psha="$(cut -d' ' -f2 <<<"${push}")"
[ -n "${psha}" ] && [ "${psha}" != "null" ] && grep -q "${psha:0:8}" <<<"${tags}" \
    && line D10 PASS "main #${push%% *} (PUSH_IMAGE=true, GitHub) pushed ${psha:0:8} to localhost:5000/eduforecast (tags: ${tags}); Docker Hub configured: ${hub} (N/A if no)" \
    || line D10 FAIL "no GitHub-sourced push build found in registry tags (${tags:-none})"

# D4 image facts of the deployed image
user="$(docker image inspect -f '{{.Config.User}}' "${img}" 2>/dev/null)"
hc="$(docker inspect -f '{{.State.Health.Status}}' eduforecast-test 2>/dev/null)"
orev="$(docker image inspect -f '{{index .Config.Labels "org.opencontainers.image.revision"}}' "${img}" 2>/dev/null)"
hist="$(docker history --no-trunc --format '{{.CreatedBy}}' "${img}" 2>/dev/null | grep -ciE 'password|token|secret|api_key|gsk_|sk-ant-' || true)"
size="$(docker image inspect -f '{{.Size}}' "${img}" 2>/dev/null)"
[ -n "${user}" ] && [ "${user}" != "root" ] && [ "${hc}" = "healthy" ] && [ "${orev}" = "${crev}" ] && [ "${hist}" = "0" ] \
    && line D4 PASS "${img}: user=${user}, health=${hc}, OCI revision=${orev:0:8}, secret-like history lines=0, size=${size} B" \
    || line D4 FAIL "user=${user:-?} health=${hc:-?} revision=${orev:0:8} history_hits=${hist} "

# D11 screenshots documented
shots_dir="docs/devops/screenshots"
undoc=""; for f in "${shots_dir}"/*.png; do grep -q "$(basename "${f}")" "${shots_dir}/README.md" || undoc="${undoc} $(basename "${f}")"; done
n="$(ls "${shots_dir}"/*.png 2>/dev/null | wc -l | tr -d ' ')"
[ "${n}" -gt 0 ] && [ -z "${undoc}" ] && line D11 PASS "${n} screenshots, all captioned in ${shots_dir}/README.md" \
                                    || line D11 FAIL "undocumented:${undoc:-none} (count ${n})"

# D12 hygiene + reproducibility from a fresh shallow clone of GitHub
tmp="$(mktemp -d)"; trap 'rm -rf "${tmp}"' EXIT
if git clone --quiet --depth 1 "https://github.com/${REPO}.git" "${tmp}/c" 2>/dev/null; then
    missing=""; for f in Jenkinsfile Dockerfile .dockerignore docs/devops/README.md docs/devops/RUNBOOK.md jenkins/docker-compose.yml data/aitu/financials_2019_2020.csv; do
        [ -e "${tmp}/c/${f}" ] || missing="${missing} ${f}"; done
    secrets="$(git -C "${tmp}/c" grep -lE 'gsk_[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|csk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}|dckr_pat_[A-Za-z0-9_-]{20,}' | grep -c . || true)"
    envs="$(git -C "${tmp}/c" ls-files | grep -E '(^|/)\.env($|\.)' | grep -vc '\.example$' || true)"
    readme="$(grep -c '^## DevOps' "${tmp}/c/README.md")"
    nshots="$(ls "${tmp}/c/docs/devops/screenshots/"*.png 2>/dev/null | wc -l | tr -d ' ')"
    [ -z "${missing}" ] && [ "${secrets}" = "0" ] && [ "${envs}" = "0" ] && [ "${readme}" -ge 1 ] && [ "${nshots}" -gt 0 ] \
        && line D12 PASS "fresh clone: key files present, ${nshots} screenshots, README DevOps section, secret patterns 0, tracked .env 0" \
        || line D12 FAIL "missing:${missing:-none} secrets=${secrets} env=${envs} readme=${readme} shots=${nshots}"
else
    line D12 FAIL "git clone of GitHub failed"
fi

# Tag (part of D14)
# no ref pattern: with a pattern GitHub omits the peeled "^{}" line of an annotated tag
peeled="$(git ls-remote --tags "https://github.com/${REPO}.git" | grep -F 'refs/tags/assignment5-final^{}' | cut -c1-8)"
mainsha="$(git ls-remote "https://github.com/${REPO}.git" refs/heads/main | cut -c1-8)"
[ -n "${peeled}" ] && line D14 PASS "annotated tag assignment5-final -> ${peeled} (main ${mainsha})" \
                   || line D14 FAIL "annotated tag assignment5-final not on GitHub"

unset JPASS JUSER
echo "failed checks: ${fails}"
exit $(( fails > 0 ))
