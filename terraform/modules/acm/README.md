# ACM Module

Creates and validates an AWS Certificate Manager certificate for the ALB
Ingress.

## Resources

- `aws_acm_certificate.main`: DNS-validated certificate for the configured
  application domain.
- `aws_route53_record.validation`: Route 53 DNS validation records.
- `aws_acm_certificate_validation.main`: waits for ACM validation to complete
  before exposing the certificate ARN.

If `domain_name` is `null` or blank, the module creates no resources and returns
`null` outputs. In that case, deployment must provide an existing certificate
ARN manually or disable HTTPS in the manifests.

## Inputs

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `domain_name` | `string` | No | Primary DNS name for the ALB certificate. |
| `route53_zone_id` | `string` | Required when `domain_name` is set and `route53_zone_name` is not set | Hosted zone where DNS validation records are created. |
| `route53_zone_name` | `string` | Required when `domain_name` is set and `route53_zone_id` is not set | Public hosted zone name to look up for DNS validation. |
| `subject_alternative_names` | `list(string)` | No | Additional DNS names for the certificate. |
| `tags` | `map(string)` | No | Additional tags for ACM resources. |

## Outputs

| Name | Description |
| --- | --- |
| `certificate_arn` | Validated ACM certificate ARN, or `null` when disabled. |
| `domain_name` | Certificate primary domain name, or `null` when disabled. |

## Used By

The root stack exposes `acm_certificate_arn`. The deployment Makefile renders it
into `k8s/ingress.yaml` as the
`alb.ingress.kubernetes.io/certificate-arn` annotation.
