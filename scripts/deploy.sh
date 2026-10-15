#!/bin/sh
set -eu

stage=${1:-dev}
region=${AWS_REGION:-ap-south-1}
stack=loan-engine-$stage

output() {
  aws cloudformation describe-stacks --region "$region" --stack-name "$stack" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

npx serverless@4 deploy --stage "$stage" --region "$region"
npx serverless@4 invoke --function migrate --stage "$stage" --region "$region"

bucket=$(output UploadBucketName)
instance=$(output N8nInstanceId)

site=$(output SiteBucketName)
echo "Publishing the UI to s3://$site/"
mkdir -p .build
printf '{"auth": {"domain": "%s", "client_id": "%s"}}\n' "$(output AuthDomain)" "$(output AuthClientId)" > .build/config.json
aws s3 sync --delete --cache-control no-cache --exclude config.json ui "s3://$site/"
aws s3 cp --cache-control no-cache .build/config.json "s3://$site/config.json"
aws cloudfront create-invalidation --distribution-id "$(output SiteDistributionId)" --paths '/*' >/dev/null

echo "Shipping n8n to s3://$bucket/deploy/"
aws s3 sync --delete --exclude '.env*' n8n "s3://$bucket/deploy/n8n/"
aws s3 cp docker-compose.yml "s3://$bucket/deploy/docker-compose.yml"
aws s3 cp infra/n8n-host.sh "s3://$bucket/deploy/n8n-host.sh"

echo "Waiting for $instance to register with SSM"
until [ "$(aws ssm describe-instance-information --region "$region" \
  --filters "Key=InstanceIds,Values=$instance" \
  --query 'InstanceInformationList[0].PingStatus' --output text)" = Online ]; do
  sleep 10
done

command=$(aws ssm send-command --region "$region" --instance-ids "$instance" \
  --document-name AWS-RunShellScript --comment "deploy n8n $stage" \
  --parameters "commands=[\"aws s3 cp s3://$bucket/deploy/n8n-host.sh /tmp/n8n-host.sh\",\"sh /tmp/n8n-host.sh $stage $bucket $region\"]" \
  --query Command.CommandId --output text)

echo "Starting n8n ($command)"
while :; do
  status=$(aws ssm get-command-invocation --region "$region" --command-id "$command" \
    --instance-id "$instance" --query Status --output text 2>/dev/null || echo Pending)
  case $status in
    Success) break ;;
    Pending | InProgress | Delayed) sleep 10 ;;
    *)
      aws ssm get-command-invocation --region "$region" --command-id "$command" \
        --instance-id "$instance" --query StandardErrorContent --output text
      exit 1
      ;;
  esac
done

echo "Deployed. Open the UI at https://$(output SiteDomainName); reach n8n with: make n8n-tunnel STAGE=$stage"
