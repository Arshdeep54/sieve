#!/bin/sh
set -eu

target=$1
stage=${2:-dev}
region=${AWS_REGION:-ap-south-1}
stack=loan-engine-$stage

output() {
  aws cloudformation describe-stacks --region "$region" --stack-name "$stack" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

instance=$(output N8nInstanceId)

case $target in
  n8n)
    echo "n8n editor on http://localhost:5679"
    aws ssm start-session --region "$region" --target "$instance" \
      --document-name AWS-StartPortForwardingSession \
      --parameters "portNumber=5678,localPortNumber=5679"
    ;;
  db)
    echo "Postgres on localhost:55433"
    aws ssm start-session --region "$region" --target "$instance" \
      --document-name AWS-StartPortForwardingSessionToRemoteHost \
      --parameters "host=$(output DatabaseHost),portNumber=5432,localPortNumber=55433"
    ;;
  *)
    echo "usage: tunnel.sh n8n|db [stage]" >&2
    exit 2
    ;;
esac
