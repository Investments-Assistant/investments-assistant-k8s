variable "cluster_name" { type = string }
variable "account_id" { type = string }
variable "oidc_provider_arn" { type = string }
variable "oidc_provider_url" { type = string }
variable "ecr_repository_arns" { type = list(string) }
variable "secrets_manager_secret_arn" { type = string }
variable "waf_webacl_arn" { type = string }
