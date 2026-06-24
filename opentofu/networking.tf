module "vpc" {
  source = "git::ssh://git@github.com/Investments-Assistant/opentofu-modules.git//vpc?ref=v1.0.0"

  cluster_name = var.cluster_name
  azs          = local.azs
}
