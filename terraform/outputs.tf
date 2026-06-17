output "cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_certificate_authority_data" {
  description = "EKS cluster CA data (base64)"
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "ecr_repository_urls" {
  description = "ECR repository URLs for all services"
  value       = module.ecr.repository_urls
}

output "allowed_ip_cidrs" {
  description = "CIDR blocks allowed to access the application"
  value       = var.allowed_ip_cidrs
  sensitive   = true
}

output "rds_endpoint" {
  description = "RDS Aurora cluster writer endpoint"
  value       = module.rds.endpoint
}

output "rds_port" {
  description = "RDS Aurora PostgreSQL port"
  value       = module.rds.port
}

output "rds_database_name" {
  description = "RDS Aurora PostgreSQL database name"
  value       = module.rds.database_name
}

output "rds_master_username" {
  description = "RDS Aurora PostgreSQL master username"
  value       = module.rds.master_username
}

output "redis_endpoint" {
  description = "ElastiCache Redis primary endpoint"
  value       = module.elasticache.endpoint
}

output "waf_webacl_arn" {
  description = "WAF WebACL ARN — paste into k8s/ingress.yaml"
  value       = module.waf.webacl_arn
}

output "acm_certificate_arn" {
  description = "ACM certificate ARN for the ALB ingress HTTPS listener"
  value       = module.acm.certificate_arn
}

output "app_domain_name" {
  description = "Application DNS name used for the ACM certificate"
  value       = module.acm.domain_name
}

output "auth_mode" {
  description = "Gateway auth mode rendered into Kubernetes manifests"
  value       = var.enable_cognito_auth ? "cognito" : "basic"
}

output "cognito_user_pool_id" {
  description = "Cognito user pool ID used by the gateway to validate tokens"
  value       = try(module.cognito[0].user_pool_id, "")
}

output "cognito_user_pool_arn" {
  description = "Cognito user pool ARN used by ALB authentication"
  value       = try(module.cognito[0].user_pool_arn, "")
}

output "cognito_user_pool_client_id" {
  description = "Cognito user pool app client ID used by ALB and gateway"
  value       = try(module.cognito[0].user_pool_client_id, "")
}

output "cognito_user_pool_domain" {
  description = "Cognito hosted UI domain prefix used by ALB authentication"
  value       = try(module.cognito[0].user_pool_domain, "")
}

output "irsa_role_arn" {
  description = "IRSA IAM role ARN — paste into k8s/serviceaccount.yaml ServiceAccount annotation"
  value       = module.secrets.irsa_role_arn
}

output "efs_id" {
  description = "EFS filesystem ID — needed if you want to pre-create the EFS storage class"
  value       = module.eks.efs_id
}

output "vpc_id" {
  value = module.vpc.vpc_id
}
