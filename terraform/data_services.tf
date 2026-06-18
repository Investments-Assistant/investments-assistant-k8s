module "rds" {
  source = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//rds?ref=v2.0.0"

  cluster_name       = var.cluster_name
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  eks_node_sg_id     = module.eks.node_security_group_id

  db_name     = var.db_name
  db_username = var.db_username
  db_password = var.db_password

  engine_version = var.aurora_postgresql_engine_version
}

module "elasticache" {
  source = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//elasticache?ref=v2.0.0"

  cluster_name       = var.cluster_name
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  eks_node_sg_id     = module.eks.node_security_group_id

  auth_token = var.redis_auth_token
  node_type  = var.redis_node_type
}
