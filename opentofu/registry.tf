module "ecr" {
  source        = "git::ssh://git@github.com/Investments-Assistant/opentofu-modules.git//ecr?ref=v0.0.1"
  service_names = ["gateway", "market-data", "news", "portfolio", "simulation", "scheduler", "forex"]
}
