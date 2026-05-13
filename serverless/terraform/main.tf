# =============================================================
# Root Module — Note-Taking App (Serverless)
# Composes child modules: database, storage, compute, cdn, dns
# =============================================================

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1" # Still needed for CloudFront certificates
}

# --- Data Sources ---

data "aws_route53_zone" "main" {
  name = var.root_domain
}

data "aws_caller_identity" "current" {}

# --- Modules ---


module "database" {
  source     = "./modules/database"
  table_name = var.project_name
  tags       = local.tags
}

module "storage" {
  source       = "./modules/storage"
  project_name = var.project_name
  tags         = local.tags
}

module "auth" {
  source                = "./modules/auth"
  project_name          = var.project_name
  aws_region            = var.aws_region
  app_domain            = var.app_domain
  cognito_domain_prefix = var.cognito_domain_prefix
  google_client_id      = var.google_client_id
  google_client_secret  = var.google_client_secret
  tags                  = local.tags
}




module "compute" {
  source = "./modules/compute"

  project_name          = var.project_name
  lambda_package        = var.lambda_package
  dynamodb_table        = module.database.table_name
  s3_bucket             = module.storage.attachments_bucket_name
  static_bucket         = module.storage.static_bucket_name
  aws_region            = var.aws_region
  cognito_user_pool_id  = module.auth.user_pool_id
  cognito_client_id     = module.auth.client_id
  cognito_client_secret = module.auth.client_secret
  cognito_domain        = module.auth.cognito_domain
  secret_key            = var.secret_key
  app_domain            = var.app_domain
  tags                  = local.tags
}


module "cdn" {
  source = "./modules/cdn"

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  app_domain         = var.app_domain
  api_gateway_url    = module.compute.api_gateway_url
  static_bucket      = module.storage.static_bucket_regional_domain
  static_bucket_id   = module.storage.static_bucket_id
  zone_id            = data.aws_route53_zone.main.zone_id
  tags               = local.tags
}

module "dns" {
  source = "./modules/dns"

  zone_id                = data.aws_route53_zone.main.zone_id
  app_domain             = var.app_domain
  cloudfront_domain_name = module.cdn.cloudfront_domain_name
  cloudfront_zone_id     = module.cdn.cloudfront_hosted_zone_id
}

# --- Locals ---

locals {
  tags = {
    Project     = var.project_name
    Environment = "production"
    ManagedBy   = "terraform"
  }
}
