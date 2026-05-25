variable "allowed_ip_cidrs" {
  type        = list(string)
  description = "CIDR blocks to allowlist (e.g. [\"1.2.3.4/32\"])"
}
