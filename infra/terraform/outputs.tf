output "vpc_id" {
  description = "ID of the CareerAI VPC"
  value       = aws_vpc.main.id
}

output "alb_dns_name" {
  description = "Public DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "ecr_repository_url" {
  description = "ECR image repository URL"
  value       = aws_ecr_repository.api.repository_url
}

output "rds_endpoint" {
  description = "Private endpoint of the RDS MySQL database"
  value       = aws_db_instance.mysql.endpoint
}

output "s3_bucket_name" {
  description = "Name of the encrypted private document storage S3 bucket"
  value       = aws_s3_bucket.documents.id
}

output "secrets_manager_arn" {
  description = "ARN of application credentials in AWS Secrets Manager"
  value       = aws_secretsmanager_secret.app_secrets.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for application logs"
  value       = aws_cloudwatch_log_group.ecs.name
}
