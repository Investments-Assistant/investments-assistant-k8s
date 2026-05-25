# Secrets Module

Creates IAM roles and policies that let Kubernetes workloads read AWS Secrets
Manager values and support ALB logging.

## Resources

- `aws_iam_role.investments_sa`: IRSA role for the Kubernetes
  `investments/investments-sa` service account.
- `aws_iam_policy.investments_sa`: policy for reading the application secret,
  pulling ECR images, and associating the WAF WebACL.
- `aws_iam_role_policy_attachment.investments_sa`: attaches the workload policy.
- `aws_iam_role.eso`: IRSA role for the External Secrets Operator service
  account in the `external-secrets` namespace.
- `aws_iam_policy.eso`: policy for reading the application secret.
- `aws_iam_role_policy_attachment.eso`: attaches the ESO policy.
- `aws_s3_bucket.alb_logs`: S3 bucket for ALB access logs.
- `aws_s3_bucket_versioning.alb_logs`: enables bucket versioning.
- `aws_s3_bucket_server_side_encryption_configuration.alb_logs`: enables AES256
  server-side encryption.
- `aws_s3_bucket_policy.alb_logs`: allows AWS load balancer log delivery using
  the regional-safe ELB log delivery service principal.

## Inputs

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `cluster_name` | `string` | Yes | Prefix for IAM role and policy names. |
| `account_id` | `string` | Yes | AWS account ID, used in log bucket policy paths. |
| `oidc_provider_arn` | `string` | Yes | EKS OIDC provider ARN for IRSA trust policies. |
| `oidc_provider_url` | `string` | Yes | EKS OIDC provider URL for IRSA trust policy conditions. |
| `ecr_repository_arns` | `list(string)` | Yes | ECR repository ARNs the workload role may pull from. |
| `secrets_manager_secret_arn` | `string` | Yes | Application secret ARN that workloads and ESO may read. |
| `waf_webacl_arn` | `string` | Yes | WAF WebACL ARN that the workload role may associate. |

## Outputs

| Name | Description |
| --- | --- |
| `irsa_role_arn` | Role ARN for the `investments-sa` Kubernetes service account. |
| `eso_role_arn` | Role ARN for the External Secrets Operator service account. |
| `alb_logs_bucket` | Name of the ALB access log bucket. |

## Used By

`k8s/serviceaccount.yaml` needs the `irsa_role_arn` output. External Secrets uses
the IAM setup to materialize the `investments-secrets` Kubernetes Secret from
AWS Secrets Manager.
