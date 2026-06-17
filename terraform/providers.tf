provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "investments-assistant"
      Environment = var.environment
      ManagedBy   = "opentofu"
    }
  }
}
