locals {
  bucket_name = "homex-public-media"
}

resource "cloudflare_r2_bucket" "media" {
  account_id    = var.cloudflare_account_id
  name          = local.bucket_name
  location      = var.bucket_location
  storage_class = "Standard"

  lifecycle {
    prevent_destroy = true
  }
}

resource "cloudflare_r2_custom_domain" "media" {
  account_id  = var.cloudflare_account_id
  bucket_name = cloudflare_r2_bucket.media.name
  domain      = var.media_domain
  enabled     = true
  zone_id     = var.cloudflare_zone_id
  min_tls     = "1.2"
}

resource "cloudflare_ruleset" "media_cache" {
  zone_id     = var.cloudflare_zone_id
  name        = "HOMEX public media cache"
  description = "Cachea únicamente objetos inmutables de productos y proformas."
  kind        = "zone"
  phase       = "http_request_cache_settings"

  rules = [
    {
      ref         = "homex_public_media_immutable"
      description = "Cache de keys UUID WebP de HOMEX"
      expression = format(
        "(http.host eq %q and (starts_with(http.request.uri.path, \"/productos/\") or starts_with(http.request.uri.path, \"/proformas/\")))",
        var.media_domain,
      )
      action = "set_cache_settings"
      action_parameters = {
        cache = true
        edge_ttl = {
          mode    = "override_origin"
          default = 31536000
          status_code_ttl = [
            {
              status_code_range = {
                from = 200
                to   = 299
              }
              value = 31536000
            },
            {
              status_code_range = {
                from = 300
                to   = 499
              }
              value = 0
            },
            {
              status_code_range = {
                from = 500
                to   = 599
              }
              value = -1
            },
          ]
        }
        browser_ttl = {
          mode    = "override_origin"
          default = 86400
        }
        cache_key = {
          ignore_query_strings_order = true
          cache_deception_armor      = true
          custom_key = {
            query_string = {
              exclude = {
                all = true
              }
            }
          }
        }
        respect_strong_etags = true
        serve_stale = {
          disable_stale_while_updating = false
        }
      }
    },
  ]

  depends_on = [cloudflare_r2_custom_domain.media]
}
