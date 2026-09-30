variable "cloudflare_account_id" {
  description = "ID de la cuenta Cloudflare propietaria de R2."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[0-9a-f]{32}$", var.cloudflare_account_id))
    error_message = "cloudflare_account_id debe ser un ID hexadecimal de 32 caracteres."
  }
}

variable "cloudflare_zone_id" {
  description = "ID de la zona que contiene el dominio público de media."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[0-9a-f]{32}$", var.cloudflare_zone_id))
    error_message = "cloudflare_zone_id debe ser un ID hexadecimal de 32 caracteres."
  }
}

variable "media_domain" {
  description = "Hostname público, sin esquema ni ruta, conectado al bucket."
  type        = string
  nullable    = false

  validation {
    condition = (
      can(regex("^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$", var.media_domain))
      && !startswith(var.media_domain, "http")
    )
    error_message = "media_domain debe ser un hostname DNS en minúsculas, sin esquema ni ruta."
  }
}

variable "bucket_location" {
  description = "Preferencia best-effort de ubicación inicial del bucket R2."
  type        = string
  default     = "wnam"

  validation {
    condition     = contains(["apac", "eeur", "enam", "weur", "wnam", "oc"], var.bucket_location)
    error_message = "bucket_location no es una ubicación R2 admitida."
  }
}
