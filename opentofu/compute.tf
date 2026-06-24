module "eks" {
  source = "git::ssh://git@github.com/Investments-Assistant/opentofu-modules.git//eks?ref=v1.0.0"

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
