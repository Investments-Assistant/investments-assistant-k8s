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

output "rds_endpoint" {
  description = "RDS Aurora cluster writer endpoint"
  value       = module.rds.endpoint
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
