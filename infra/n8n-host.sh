#!/bin/sh
set -eu

stage=$1
bucket=$2
region=$3
dir=/opt/loan-engine

cloud-init status --wait
mkdir -p "$dir"
cd "$dir"
aws s3 sync --delete --exclude .env "s3://$bucket/deploy/" .

aws ssm get-parameters-by-path --region "$region" --path "/loan-engine/$stage" --with-decryption \
  --query 'Parameters[].[Name,Value]' --output text |
  while IFS="$(printf '\t')" read -r name value; do
    printf '%s=%s\n' "$(basename "$name" | tr 'a-z-' 'A-Z_')" "$value"
  done > .env

cat >> .env <<EOF
AWS_REGION=$region
DB_PORT=5432
DB_NAME=loan_engine
DB_USER=loan_engine
DB_SSL=require
OPENAI_MODEL=gpt-4.1-mini
DEMO_LIMIT=5
EOF
chmod 600 .env

docker compose up -d --force-recreate n8n
