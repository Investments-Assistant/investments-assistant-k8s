terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  backend "s3" {
    # Created by the core-infra Terraform (already exists)
    bucket  = "invass-investments-assistant-k8s-terraform-state-20260508003100"
    key     = "investments-k8s/terraform.tfstate"
    region  = "eu-south-2"
    encrypt = true
  }
}
