output "certificate_arn" {
  description = "Validated ACM certificate ARN, or null when certificate creation is disabled."
  value       = try(aws_acm_certificate_validation.main[0].certificate_arn, null)
}

output "domain_name" {
  description = "Certificate primary domain name, or null when disabled."
  value       = local.domain_name
}
