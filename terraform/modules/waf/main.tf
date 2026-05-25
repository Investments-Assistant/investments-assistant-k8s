terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

# WAF must be regional (not CloudFront) to attach to an ALB
resource "aws_wafv2_ip_set" "allowed" {
  name               = "investments-allowed-ips"
  scope              = "REGIONAL"
  ip_address_version = "IPV4"
  addresses          = var.allowed_ip_cidrs

  lifecycle { create_before_destroy = true }
}

resource "aws_wafv2_web_acl" "main" {
  name  = "investments-allowlist"
  scope = "REGIONAL"

  default_action {
    block {}
  }

  rule {
    name     = "AllowMyIP"
    priority = 1

    action {
      allow {}
    }

    statement {
      ip_set_reference_statement {
        arn = aws_wafv2_ip_set.allowed.arn
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AllowMyIP"
      sampled_requests_enabled   = true
    }
  }

  # Allow health check from within the cluster (ALB targets)
  rule {
    name     = "AllowHealthCheck"
    priority = 2

    action {
      allow {}
    }

    statement {
      byte_match_statement {
        field_to_match {
          uri_path {}
        }
        positional_constraint = "STARTS_WITH"
        search_string         = "/api/health"
        text_transformation {
          priority = 0
          type     = "NONE"
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = false
      metric_name                = "AllowHealthCheck"
      sampled_requests_enabled   = false
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "investments-waf"
    sampled_requests_enabled   = true
  }
}

resource "aws_cloudwatch_log_group" "waf" {
  name              = "aws-waf-logs-investments"
  retention_in_days = 30
}

resource "aws_wafv2_web_acl_logging_configuration" "main" {
  log_destination_configs = [trimsuffix(aws_cloudwatch_log_group.waf.arn, ":*")]
  resource_arn            = aws_wafv2_web_acl.main.arn
}
