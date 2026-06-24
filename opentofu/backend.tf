terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    # Created by core-infra OpenTofu (already exists)
    bucket       = "invass-investments-assistant-k8s-tt-state"
    key          = "investments-k8s/opentofu.tfstate"
    region       = "eu-south-2"
    use_lockfile = true
    encrypt      = true
  }
}
