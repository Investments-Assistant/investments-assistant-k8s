locals {
  account_id         = data.aws_caller_identity.current.account_id
  azs                = slice(data.aws_availability_zones.available.names, 0, 3)
  app_domain_enabled = var.app_domain_name != null && trimspace(var.app_domain_name) != ""

  cognito_callback_url = local.app_domain_enabled ? [
    "https://${trimspace(var.app_domain_name)}/oauth2/idpresponse"
  ] : []

  cognito_logout_url = local.app_domain_enabled ? [
    "https://${trimspace(var.app_domain_name)}/"
  ] : []
}
