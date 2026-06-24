module "ecr" {
  source        = "git::ssh://git@github.com/Investments-Assistant/opentofu-modules.git//ecr?ref=v1.0.0"
  service_names = ["gateway", "market-data", "news", "portfolio", "simulation", "scheduler", "forex"]
}
