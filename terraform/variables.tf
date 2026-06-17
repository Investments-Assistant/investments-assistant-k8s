variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-south-2"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "investments-assistant"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "allowed_ip_cidrs" {
  description = "Public CIDR blocks allowed to access the ALB, usually your VPN egress IPv4 as x.x.x.x/32"
  type        = list(string)
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "investments"
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "investments"
}

variable "db_password" {
  description = "PostgreSQL master password (stored in Secrets Manager)"
  type        = string
  sensitive   = true
}

variable "app_secret_values" {
  description = "Additional key/value pairs written to the investments/prod Secrets Manager secret"
  type        = map(string)
  sensitive   = true
  default     = {}
}

variable "redis_auth_token" {
  description = "ElastiCache Redis auth token"
  type        = string
  sensitive   = true
  default     = null

  validation {
    condition = (
      var.redis_auth_token == null ||
      trimspace(var.redis_auth_token) == "" ||
      can(regex("^[^@\"/]{16,128}$", var.redis_auth_token))
    )
    error_message = "redis_auth_token must be null, empty, or 16-128 characters excluding @, double quote, and /."
  }
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "aurora_postgresql_engine_version" {
  description = "Optional Aurora PostgreSQL engine version. Set to null to let AWS choose the regional default."
  type        = string
  default     = null
}

variable "app_domain_name" {
  description = "Optional public DNS name for the ALB HTTPS certificate"
  type        = string
  default     = null
}

variable "app_route53_zone_id" {
  description = "Route 53 hosted zone ID used to validate app_domain_name"
  type        = string
  default     = null
}

variable "app_route53_zone_name" {
  description = "Route 53 public hosted zone name used to validate app_domain_name when app_route53_zone_id is not set"
  type        = string
  default     = null
}

variable "app_certificate_subject_alternative_names" {
  description = "Optional additional DNS names for the ALB HTTPS certificate"
  type        = list(string)
  default     = []
}

variable "enable_cognito_auth" {
  description = "Enable Cognito/ALB authentication for the public gateway. Requires app_domain_name and HTTPS."
  type        = bool
  default     = false
}

variable "cognito_domain_prefix" {
  description = "Optional Cognito hosted UI domain prefix. Must be unique in the AWS region."
  type        = string
  default     = null
}

variable "cognito_user_groups" {
  description = "Cognito user groups mapped by the gateway to viewer, investor, and admin roles."
  type = map(object({
    description = string
    precedence  = number
  }))
  default = {
    viewer = {
      description = "Can chat with the assistant about news only."
      precedence  = 30
    }
    investor = {
      description = "Can use market data, news, simulations, and reports, but not portfolio tools."
      precedence  = 20
    }
    admin = {
      description = "Can use every assistant service and administrative trading controls."
      precedence  = 10
    }
  }
}

variable "node_instance_type" {
  description = "EC2 instance type for EKS worker nodes"
  type        = string
  default     = "t3.medium"
}

variable "node_min_size" {
  type    = number
  default = 2
}

variable "node_max_size" {
  type    = number
  default = 5
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "enable_llm_node_group" {
  description = "Whether to create a dedicated EKS managed node group for the self-hosted LLM pod"
  type        = bool
  default     = true
}

variable "llm_node_instance_type" {
  description = "EC2 instance type for the dedicated LLM worker node group"
  type        = string
  default     = "t3.xlarge"
}

variable "llm_node_min_size" {
  type    = number
  default = 1
}

variable "llm_node_max_size" {
  type    = number
  default = 2
}

variable "llm_node_desired_size" {
  type    = number
  default = 1
}

variable "k8s_version" {
  description = "Kubernetes version for EKS"
  type        = string
  default     = "1.33"
}
