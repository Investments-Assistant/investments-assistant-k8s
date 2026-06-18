module "cloudfront_https" {
  count  = local.cloudfront_https_enabled ? 1 : 0
  source = "git::ssh://git@github.com/Investments-Assistant/terraform-modules.git//cloudfront_https?ref=v2.0.0"

  name                = var.cluster_name
  origin_domain_name  = local.cloudfront_origin_domain_name
  price_class         = var.cloudfront_price_class
  wait_for_deployment = var.cloudfront_wait_for_deployment
  tags = {
    Name = "${var.cluster_name}-cloudfront"
  }
}
