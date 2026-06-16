data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" { state = "available" }

locals {
  account_id = data.aws_caller_identity.current.account_id
  azs        = slice(data.aws_availability_zones.available.names, 0, 3)
}

# ── VPC ──────────────────────────────────────────────────────────────────────
module "vpc" {
  source = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//vpc?ref=v1.0.0"

  cluster_name = var.cluster_name
  azs          = local.azs
}

# ── EKS ──────────────────────────────────────────────────────────────────────
module "eks" {
  source = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//eks?ref=v1.0.0"

  cluster_name       = var.cluster_name
  k8s_version        = var.k8s_version
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids

  node_instance_type = var.node_instance_type
  node_min_size      = var.node_min_size
  node_max_size      = var.node_max_size
  node_desired_size  = var.node_desired_size

  enable_llm_node_group  = var.enable_llm_node_group
  llm_node_instance_type = var.llm_node_instance_type
  llm_node_min_size      = var.llm_node_min_size
  llm_node_max_size      = var.llm_node_max_size
  llm_node_desired_size  = var.llm_node_desired_size

  aws_region = var.aws_region
}

# ── RDS Aurora PostgreSQL Serverless v2 ──────────────────────────────────────
module "rds" {
  source = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//rds?ref=v1.0.0"

  cluster_name       = var.cluster_name
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  eks_node_sg_id     = module.eks.node_security_group_id

  db_name     = var.db_name
  db_username = var.db_username
  db_password = var.db_password

  engine_version = var.aurora_postgresql_engine_version
}

# ── ElastiCache Redis ─────────────────────────────────────────────────────────
module "elasticache" {
  source = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//elasticache?ref=v1.0.0"

  cluster_name       = var.cluster_name
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  eks_node_sg_id     = module.eks.node_security_group_id

  auth_token = var.redis_auth_token
  node_type  = var.redis_node_type
}

# ── ECR Repositories ─────────────────────────────────────────────────────────
module "ecr" {
  source        = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//ecr?ref=v1.0.0"
  service_names = ["gateway", "market-data", "news", "portfolio", "simulation", "scheduler", "forex"]
}

# ── WAF WebACL (IP allowlist for ALB) ────────────────────────────────────────
module "waf" {
  source           = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//waf?ref=v1.0.0"
  allowed_ip_cidrs = var.allowed_ip_cidrs
}

# ── ACM certificate for ALB HTTPS ────────────────────────────────────────────
module "acm" {
  source = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//acm?ref=v1.0.0"

  domain_name               = var.app_domain_name
  route53_zone_id           = var.app_route53_zone_id
  route53_zone_name         = var.app_route53_zone_name
  subject_alternative_names = var.app_certificate_subject_alternative_names
  tags = {
    Name = "${var.cluster_name}-alb-certificate"
  }
}

# ── Secrets Manager + IRSA ───────────────────────────────────────────────────
module "secrets" {
  source = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//secrets?ref=v1.0.0"

  cluster_name               = var.cluster_name
  account_id                 = local.account_id
  oidc_provider_arn          = module.eks.oidc_provider_arn
  oidc_provider_url          = module.eks.oidc_provider_url
  ecr_repository_arns        = module.ecr.repository_arns
  secrets_manager_secret_arn = aws_secretsmanager_secret.investments.arn
  waf_webacl_arn             = module.waf.webacl_arn
}

# ── Secrets Manager secret consumed by External Secrets Operator ─────────────
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
