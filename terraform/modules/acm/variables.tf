variable "domain_name" {
  description = "Domain name for the ALB TLS certificate. Set to null to skip certificate creation."
  type        = string
  default     = null

  validation {
    condition = (
      var.domain_name == null ||
      trimspace(var.domain_name) == "" ||
      can(regex("^[A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9]$", trimspace(var.domain_name)))
    )
    error_message = "domain_name must be null, empty, or a valid DNS name."
  }
}

variable "route53_zone_id" {
  description = "Route 53 hosted zone ID where DNS validation records will be created."
  type        = string
  default     = null

  validation {
    condition = (
      var.domain_name == null ||
      trimspace(var.domain_name) == "" ||
      (var.route53_zone_id != null && trimspace(var.route53_zone_id) != "") ||
      (var.route53_zone_name != null && trimspace(var.route53_zone_name) != "")
    )
    error_message = "route53_zone_id or route53_zone_name is required when domain_name is set."
  }
}

variable "route53_zone_name" {
  description = "Route 53 public hosted zone name to look up when route53_zone_id is not provided."
  type        = string
  default     = null
}

variable "subject_alternative_names" {
  description = "Optional additional DNS names for the certificate."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Additional tags for ACM resources."
  type        = map(string)
  default     = {}
}
