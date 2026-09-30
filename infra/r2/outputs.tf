output "bucket_name" {
  description = "Nombre contractual del bucket de media."
  value       = cloudflare_r2_bucket.media.name
}

output "media_public_domain" {
  description = "Dominio público que debe usar HOMEX_MEDIA_PUBLIC_DOMAIN."
  value       = cloudflare_r2_custom_domain.media.domain
}

output "custom_domain_status" {
  description = "Estado de ownership y TLS informado por Cloudflare."
  value       = cloudflare_r2_custom_domain.media.status
}
