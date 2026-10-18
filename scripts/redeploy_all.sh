#!/usr/bin/env bash
# The final redeploy of the radar, in order: lake check, Cloud Run (Cloud Build), static export,
# graph views, web build, Netlify, live check. Dry run by default: it runs the read-only checks and
# prints every deploy command without running it. `--run` deploys (approved in advance by the
# orchestrator for the 05:30-06:00 run; anything else changing the live service needs the maintainer).
#
#   bash scripts/redeploy_all.sh          # dry run
#   bash scripts/redeploy_all.sh --run    # deploy
#   make redeploy-all ARGS=--run
#   RADAR_SOURCE=gdelt make redeploy-all  # v0.2 (GDELT orgs and themes) instead of the AI radar
#
# RADAR_SOURCE (default ai) picks the radar: the API's env var on Cloud Run, the static fallback's
# tables and the graph views (export_views --ai). The scores file checked in steps 1-2 follows it.
#
# The Cloud Run URL and the project come from gcloud and .env at run time; nothing is written to git.
# Memory: the image is built by Cloud Build, never by local Docker.
set -euo pipefail

RUN=0
[[ "${1:-}" == "--run" ]] && RUN=1
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
REGION=us-central1
SERVICE=radar-api
SOURCE="${RADAR_SOURCE:-ai}"
case "$SOURCE" in
  ai) SCORES_TABLE=topic_ai_scores_weekly; VIEWS_FLAGS="--ai" ;;
  gdelt) SCORES_TABLE=topic_scores_weekly; VIEWS_FLAGS="" ;;
  *) printf 'STOP: RADAR_SOURCE must be ai or gdelt, not %s\n' "$SOURCE" >&2; exit 1 ;;
esac
SCORES="lake/gold/$SCORES_TABLE.parquet"
STAGED="build/cloudrun/lake/gold/$SCORES_TABLE.parquet"

step() { printf '\n== %s\n' "$*"; }
run() {  # deploy commands: printed in a dry run, executed with --run
  printf '   $ %s\n' "$*"
  if [[ $RUN == 1 ]]; then eval "$@"; fi
}
envval() { { grep "^$1=" .env || true; } | cut -d= -f2-; }  # empty, not a pipefail exit, if absent
fail() { printf 'STOP: %s\n' "$*" >&2; exit 1; }

step "0. preconditions (read-only, always run)"
PROJECT="$(envval GCP_PROJECT_ID)"
[[ -n "$PROJECT" ]] || fail "GCP_PROJECT_ID missing in .env"
[[ "$(gcloud config get-value project 2>/dev/null)" == "$PROJECT" ]] \
  || fail "gcloud's project is not GCP_PROJECT_ID (run: gcloud config set project \$GCP_PROJECT_ID)"
SITE_ID="$(envval NETLIFY_SITE_ID)"
[[ -n "$SITE_ID" ]] || fail "NETLIFY_SITE_ID missing in .env"
API_URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
MIN_INSTANCES="$(gcloud run services describe "$SERVICE" --region "$REGION" \
  --format='value(spec.template.metadata.annotations."autoscaling.knative.dev/minScale")')"
MIN_INSTANCES="${MIN_INSTANCES:-0}"
echo "   project ok, Netlify site id set, API url resolved, current min-instances: $MIN_INSTANCES"
echo "   radar source: $SOURCE (scores $SCORES_TABLE)"
[[ -f "$SCORES" ]] || fail "$SCORES missing"

step "1. $SCORES_TABLE is stable (no writer mid-run)"
AGE_S=$(( $(date +%s) - $(stat -f %m "$SCORES") ))
SUM1="$(md5 -q "$SCORES")"; sleep 5; SUM2="$(md5 -q "$SCORES")"
[[ "$SUM1" == "$SUM2" ]] || fail "$SCORES changed while checking: WS4 is still writing"
(( AGE_S >= 120 )) || fail "$SCORES was written ${AGE_S}s ago; wait 2 minutes after WS4's signal"
echo "   md5 $SUM1, last written ${AGE_S}s ago"

step "2. Cloud Run: stage the image context and deploy with Cloud Build (keeps min-instances)"
run make deploy-cloudrun MIN_INSTANCES="$MIN_INSTANCES" RADAR_SOURCE="$SOURCE"
if [[ $RUN == 1 ]]; then
  [[ "$(md5 -q "$STAGED")" == "$SUM1" ]] || fail "the image shipped a different $SCORES_TABLE"
  echo "   shipped $SCORES_TABLE md5 matches the lake"
fi

step "3. static fallback from the same lake (top 10s, timelines, rings, evidence)"
run make deploy-static RADAR_SOURCE="$SOURCE"

# export_static.py deletes web/public/data, including the views JSON. The no-WebGL image is
# tracked at web/public/fallback/temporal.png, so that wipe does not remove it.
step "3b. graph views, rewritten after the static export wipes web/public/data"
run "RADAR_PROFILE=full uv run --extra graph python -m graph.export_views $VIEWS_FLAGS"
if [[ "$VIEWS_FLAGS" == *--ai* ]]; then
  # Gate: every week x lens x important topic of the AI graph must be covered, or no deploy.
  run "RADAR_PROFILE=full uv run python -m graph.check_ai_views"
fi

step "4. web build pointing at the API"
run make deploy-web API_URL="$API_URL"

step "5. Netlify production deploy"
run "npx --yes netlify-cli deploy --dir web/dist --site \"$SITE_ID\" --prod"
run "rm -rf .netlify"

step "6. live check (reads only; add a chat turn with make demo-check ARGS=--chat)"
run make demo-check ARGS= RADAR_SOURCE="$SOURCE"   # clear the caller's ARGS=--run, which make passes down

if [[ $RUN == 1 ]]; then
  printf '\nDONE: redeployed; demo-check above must read 7/7 passed.\n'
else
  printf '\nDRY RUN: preconditions and the lake check passed; nothing was deployed.\n'
fi
