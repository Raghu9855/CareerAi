resource "aws_secretsmanager_secret" "app_secrets" {
  name                    = "careerai/${var.environment}/app-secrets"
  description             = "Production environment credentials, tokens, and database connection strings for CareerAI"
  recovery_window_in_days = 7

  tags = {
    Name = "careerai-${var.environment}-secrets"
  }
}

# Example secret JSON structure (values populated manually or via AWS CLI)
resource "aws_secretsmanager_secret_version" "app_secrets_template" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    SECRET_KEY             = "REPLACE_WITH_SECURE_RANDOM_SECRET_KEY_MIN_32_CHARS"
    DATABASE_URL           = "mysql+asyncmy://${aws_db_instance.mysql.username}:${random_password.db_password.result}@${aws_db_instance.mysql.endpoint}/${aws_db_instance.mysql.db_name}"
    OPENAI_API_KEY         = "REPLACE_WITH_OPENAI_OR_LLM_KEY"
    S3_BUCKET_NAME         = aws_s3_bucket.documents.id
    AWS_REGION             = var.aws_region
    STORAGE_BACKEND        = "s3"
    LLM_PROVIDER           = "openai"
    VECTOR_STORE_TYPE      = "memory"
  })
}
