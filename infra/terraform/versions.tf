terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  # Uncomment and configure for remote state management
  # backend "s3" {
  #   bucket         = "careerai-terraform-state-prod"
  #   key            = "careerai/prod/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "careerai-terraform-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "CareerAI"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}
