module "secrets" {
  source = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//secrets?ref=v1.5.0"

  cluster_name               = var.cluster_name
  account_id                 = local.account_id
  oidc_provider_arn          = module.eks.oidc_provider_arn
  oidc_provider_url          = module.eks.oidc_provider_url
  ecr_repository_arns        = module.ecr.repository_arns
  secrets_manager_secret_arn = aws_secretsmanager_secret.investments.arn
  waf_webacl_arn             = module.waf.webacl_arn
}

resource "aws_secretsmanager_secret" "investments" {
  name                    = "investments/prod"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "investments" {
  secret_id = aws_secretsmanager_secret.investments.id
  secret_string = jsonencode(merge(var.app_secret_values, {
    POSTGRES_PASSWORD = var.db_password
  }))
}
