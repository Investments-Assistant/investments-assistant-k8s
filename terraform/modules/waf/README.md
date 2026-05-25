# WAF Module

Creates a regional AWS WAF WebACL intended to be attached to the public
Application Load Balancer created by AWS Load Balancer Controller.

## Resources

- `aws_wafv2_ip_set.allowed`: IPv4 allowlist from `allowed_ip_cidrs`.
- `aws_wafv2_web_acl.main`: WebACL with a default block action.
- `aws_cloudwatch_log_group.waf`: log group for WAF logs. The name starts with
  `aws-waf-logs-` because AWS WAF requires that prefix for CloudWatch Logs
  destinations.
- `aws_wafv2_web_acl_logging_configuration.main`: sends WebACL logs to CloudWatch.

## Rules

- `AllowMyIP`: allows requests from the configured IP set.
- `AllowHealthCheck`: allows requests where the URI path starts with
  `/api/health`, so ALB health checks can pass.

All other requests are blocked by default.

## Inputs

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `allowed_ip_cidrs` | `list(string)` | Yes | IPv4 CIDR blocks allowed to access the public ALB. |

## Outputs

| Name | Description |
| --- | --- |
| `webacl_arn` | ARN to place in the ALB ingress annotation. |
| `webacl_id` | WebACL ID. |

## Used By

`k8s/ingress.yaml` references the WebACL ARN through the
`alb.ingress.kubernetes.io/wafv2-acl-arn` annotation.
