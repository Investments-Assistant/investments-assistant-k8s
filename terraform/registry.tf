module "ecr" {
  source        = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//ecr?ref=v1.1.0"
  service_names = ["gateway", "market-data", "news", "portfolio", "simulation", "scheduler", "forex"]
}
