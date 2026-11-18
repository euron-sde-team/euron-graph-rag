# 0006: Floci provides AWS locally, provisioned by the production Terraform

Status: accepted

## Context

The application calls S3 (originals), SQS (jobs, dead-letter queue), KMS and Secrets Manager.
Developers and CI must run all of it without an AWS account, and the infrastructure code that
builds production should not be a different, untested path from the local one.

## Decision

Run `floci/floci` (MIT) on the Compose network as the AWS endpoint. A one-shot `terraform`
container applies `infra/terraform/envs/local-floci` against it before the API and worker
start, using the same modules as `aws-dev` and `aws-prod`. The application reads
`AWS_ENDPOINT_URL` and otherwise behaves identically. The integration suite provisions its own
uniquely named bucket, key and queues on the same emulator.

## Consequences

- `make up` exercises the real S3 and SQS code paths, including the dead-letter redrive.
- A change to a Terraform module is validated locally by the stack that consumes it.
- The emulator is pinned; behaviour it does not model (IAM policies, some bucket features) is
  covered by `terraform validate`, tflint and checkov instead.
- Production refuses `AWS_ENDPOINT_URL`, so the override cannot leak into a real deployment.
