#!/bin/sh
set -e

credentials=$(mktemp)
node /opt/loan-engine/credentials.js > "$credentials"
n8n import:credentials --input="$credentials"
rm -f "$credentials"

n8n import:workflow --separate --input=/opt/loan-engine/workflows
for workflow in /opt/loan-engine/workflows/*.json; do
  [ -e "$workflow" ] || continue
  id=$(node -e "console.log(require('$workflow').id)")
  n8n publish:workflow --id="$id"
done

exec /docker-entrypoint.sh start
