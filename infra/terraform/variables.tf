variable "aws_region" {
  description = "Target AWS deployment region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment name (production, staging, dev)"
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "CIDR block for the dedicated CareerAI VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "domain_name" {
  description = "Custom domain name for the API service (e.g. api.careerai.io)"
  type        = string
  default     = "api.careerai.internal"
}

variable "certificate_arn" {
  description = "AWS Certificate Manager (ACM) ARN for HTTPS ALB listener"
  type        = string
  default     = ""
}

variable "db_instance_class" {
  description = "RDS MySQL instance computation tier"
  type        = string
  default     = "db.t4g.small"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB for RDS MySQL"
  type        = number
  default     = 20
}

variable "container_cpu" {
  description = "Fargate task CPU units (256, 512, 1024, 2048)"
  type        = number
  default     = 512
}

variable "container_memory" {
  description = "Fargate task RAM in MB (1024, 2048, 4096)"
  type        = number
  default     = 1024
}

variable "desired_count" {
  description = "Initial number of ECS task replicas"
  type        = number
  default     = 2
}
