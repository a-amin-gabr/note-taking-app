# =============================================================
# Module: dns — Route 53 Records
# =============================================================

resource "aws_route53_record" "app" {
  zone_id = var.zone_id
  name    = var.app_domain
  type    = "A"

  alias {
    name                   = var.cloudfront_domain_name
    zone_id                = var.cloudfront_zone_id
    evaluate_target_health = false
  }

  allow_overwrite = true
}

