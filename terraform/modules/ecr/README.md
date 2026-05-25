# ECR Module

Creates one Amazon ECR repository per application service.

## Resources

- `aws_ecr_repository.services`: repositories named `investments-<service>`.
- `aws_ecr_lifecycle_policy.services`: retention policy that keeps the latest
  10 images and expires older images.

Each repository uses mutable tags, scan-on-push, and AES256 encryption.

## Inputs

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `service_names` | `list(string)` | Yes | Service names used to create repositories named `investments-<name>`. |

## Outputs

| Name | Description |
| --- | --- |
| `repository_urls` | Map of service name to ECR repository URL. |
| `repository_arns` | List of ECR repository ARNs. |

## Used By

The Makefile and GitHub Actions workflows push service images to these
repositories. The secrets module uses the repository ARNs when building IAM
permissions for image pulls.
