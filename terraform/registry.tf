module "ecr" {
  source        = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//ecr?ref=v2.0.0"
  service_names = ["gateway", "market-data", "news", "portfolio", "simulation", "scheduler", "forex"]
}
