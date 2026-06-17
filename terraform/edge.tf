module "waf" {
  source           = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//waf?ref=v1.5.0"
  allowed_ip_cidrs = var.allowed_ip_cidrs
}

module "acm" {
  source = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//acm?ref=v1.5.0"

  domain_name               = var.app_domain_name
  route53_zone_id           = var.app_route53_zone_id
  route53_zone_name         = var.app_route53_zone_name
  subject_alternative_names = var.app_certificate_subject_alternative_names
  tags = {
    Name = "${var.cluster_name}-alb-certificate"
  }
}

resource "terraform_data" "cognito_https_guard" {
  count = var.enable_cognito_auth ? 1 : 0

  input = var.app_domain_name

  lifecycle {
    precondition {
      condition     = local.app_domain_enabled
      error_message = "enable_cognito_auth requires app_domain_name so ALB authentication can run on HTTPS."
    }
  }
}

module "cognito" {
  count      = var.enable_cognito_auth ? 1 : 0
  source     = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//cognito?ref=v1.5.0"
  depends_on = [terraform_data.cognito_https_guard]

  cluster_name  = var.cluster_name
  domain_prefix = var.cognito_domain_prefix
  callback_urls = local.cognito_callback_url
  logout_urls   = local.cognito_logout_url
  groups        = var.cognito_user_groups
}
