#!/usr/bin/env bash
# Pre-push audit: what would reach GitHub, and does any of it look like a secret or data?
# Read-only. Usage: scripts/devops/prepush_audit.sh [base-ref]   (default origin/main)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BASE="${1:-origin/main}"
cd "${ROOT}"
status=0
PATTERN='gsk_[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|csk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}|dckr_pat_[A-Za-z0-9_-]{20,}'
ASSIGN='^\+?[^#]*(API_KEY|TOKEN|PASSWORD|SECRET)[A-Z_]*[[:space:]]*=[[:space:]]*["'\'']?[A-Za-z0-9_\-]{16,}'

echo "== commits ${BASE}..HEAD"
git log --oneline "${BASE}..HEAD" | sed 's/^/  /'
echo "== diff stat ${BASE}..HEAD"
git diff --stat "${BASE}..HEAD" | tail -n 1

echo "== secret patterns in the diff"
hits="$(git diff "${BASE}..HEAD" | grep -nE "${PATTERN}" || true)"
assign="$(git diff "${BASE}..HEAD" | grep -E '^\+' | grep -nE "${ASSIGN}" || true)"
if [ -n "${hits}${assign}" ]; then
    echo "  FOUND (values not shown):"; printf '%s\n%s\n' "${hits}" "${assign}" | cut -d: -f1 | sed 's/^/  diff line /'
    status=1
else
    echo "  none"
fi

echo "== secret patterns in tracked files"
files="$(git grep -lE "${PATTERN}" HEAD -- . || true)"
if [ -n "${files}" ]; then echo "  FOUND in: ${files}"; status=1; else echo "  none"; fi

echo "== secret files must be untracked"
for f in .env .env.local jenkins/.env.jenkins .streamlit/secrets.toml; do
    if git ls-files --error-unmatch "${f}" >/dev/null 2>&1; then
        echo "  TRACKED: ${f}"; status=1
    else
        echo "  untracked: ${f}$( [ -e "${f}" ] && echo ' (exists locally, ignored)' )"
    fi
done
echo "  tracked .env* files: $(git ls-files | grep -E '(^|/)\.env' | tr '\n' ' ')"

echo "== tracked data-like files (csv/json/parquet/pkl/xlsx/zip), size"
git ls-files | grep -E '\.(csv|json|parquet|pkl|xlsx|zip)$' | while read -r f; do
    printf '  %8s  %s\n' "$(wc -c < "${f}" | tr -d ' ')" "${f}"
done

echo
echo "WARNING: Repository is PUBLIC; decide before pushing whether data/aitu/financials_2019_2020.csv and the advisor-experiment materials may be published."
exit "${status}"
