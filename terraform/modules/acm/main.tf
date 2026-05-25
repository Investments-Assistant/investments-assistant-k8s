terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

locals {
  enabled          = var.domain_name != null && trimspace(var.domain_name) != ""
  domain_name      = local.enabled ? trimspace(var.domain_name) : null
  provided_zone_id = var.route53_zone_id != null && trimspace(var.route53_zone_id) != "" ? trimspace(var.route53_zone_id) : null
  lookup_zone      = local.enabled && local.provided_zone_id == null
  route53_zone_id  = local.enabled ? (local.provided_zone_id != null ? local.provided_zone_id : try(data.aws_route53_zone.selected[0].zone_id, null)) : null
}

data "aws_route53_zone" "selected" {
  count = local.lookup_zone ? 1 : 0

  name         = var.route53_zone_name
  private_zone = false
}

resource "aws_acm_certificate" "main" {
  count = local.enabled ? 1 : 0

  domain_name               = local.domain_name
  subject_alternative_names = var.subject_alternative_names
  validation_method         = "DNS"

  tags = merge(var.tags, {
    Name = local.domain_name
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "validation" {
  for_each = local.enabled ? {
    for dvo in aws_acm_certificate.main[0].domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  } : {}

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = local.route53_zone_id
}

resource "aws_acm_certificate_validation" "main" {
  count = local.enabled ? 1 : 0

  certificate_arn         = aws_acm_certificate.main[0].arn
  validation_record_fqdns = [for record in aws_route53_record.validation : record.fqdn]
}
