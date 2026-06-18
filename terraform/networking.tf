module "vpc" {
  source = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//vpc?ref=v2.0.0"

  cluster_name = var.cluster_name
  azs          = local.azs
}
