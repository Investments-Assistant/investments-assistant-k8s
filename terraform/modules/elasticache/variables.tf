variable "cluster_name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "eks_node_sg_id" {
  type = string
}

variable "node_type" {
  description = "ElastiCache node type for Redis. Override this when a region does not support the default."
  type        = string
  default     = "cache.t3.micro"
}

variable "auth_token" {
  type      = string
  sensitive = true
  default   = null

  validation {
    condition = (
      var.auth_token == null ||
      trimspace(var.auth_token) == "" ||
      can(regex("^[^@\"/]{16,128}$", var.auth_token))
    )
    error_message = "auth_token must be null, empty, or 16-128 characters excluding @, double quote, and /."
  }
}
