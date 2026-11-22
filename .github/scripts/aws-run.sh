#!/usr/bin/env bash
# Runs a shell command on the Lumina IQ EC2 server through SSM and prints its output.
# Usage: aws-run.sh "<command>" [timeout-seconds]
set -euo pipefail
CMD="$1"; TIMEOUT="${2:-1500}"
IID=$(aws ec2 describe-instances --filters Name=tag:Name,Values=luminaiq-server Name=instance-state-name,Values=running \
      --query "Reservations[0].Instances[0].InstanceId" --output text)
[ -n "$IID" ] && [ "$IID" != "None" ] || { echo "::error::No running luminaiq-server instance"; exit 1; }
PARAMS=$(jq -n --arg c "$CMD" --arg t "$TIMEOUT" '{commands:[$c], executionTimeout:[$t]}')
CID=$(aws ssm send-command --instance-ids "$IID" --document-name AWS-RunShellScript \
      --parameters "$PARAMS" --timeout-seconds 600 --query Command.CommandId --output text)
echo "SSM command $CID on $IID"
while :; do
  sleep 10
  S=$(aws ssm get-command-invocation --command-id "$CID" --instance-id "$IID" --query Status --output text 2>/dev/null || echo Pending)
  case "$S" in Pending|InProgress|Delayed) continue ;; esac
  break
done
aws ssm get-command-invocation --command-id "$CID" --instance-id "$IID" --query StandardOutputContent --output text | tail -c 20000
echo "--- stderr"
aws ssm get-command-invocation --command-id "$CID" --instance-id "$IID" --query StandardErrorContent --output text | tail -c 8000
[ "$S" = "Success" ] || { echo "::error::Server command ended: $S"; exit 1; }
