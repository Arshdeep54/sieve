#!/bin/sh
set -eu

env_file=$1
stage=${2:-dev}
region=${AWS_REGION:-ap-south-1}

for key in DB_PASSWORD N8N_ENCRYPTION_KEY WEBHOOK_SECRET OPENAI_API_KEY \
  SES_ACCESS_KEY_ID SES_SECRET_ACCESS_KEY SES_FROM GMAIL_BASE; do
  value=$(grep -E "^$key=" "$env_file" | tail -n 1 | cut -d= -f2-)
  if [ -z "$value" ]; then
    echo "skipped $key, it is empty in $env_file"
    continue
  fi
  name=/loan-engine/$stage/$(echo "$key" | tr 'A-Z_' 'a-z-')
  aws ssm put-parameter --region "$region" --name "$name" --type SecureString \
    --overwrite --value "$value" > /dev/null
  echo "stored $name"
done
