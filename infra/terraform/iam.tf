# -----------------------------------------------------------------------------
# ECS Task Execution Role (Pulling images, pushing logs, fetching secrets)
# -----------------------------------------------------------------------------
resource "aws_iam_role" "ecs_execution_role" {
  name = "careerai-${var.environment}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "ecs-tasks.amazonaws.com" }
      }
    ]
  })
}

# Attach standard AWS managed execution policy
resource "aws_iam_role_policy_attachment" "ecs_execution_standard" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Policy allowing ECS execution to fetch Secrets Manager values
resource "aws_iam_policy" "ecs_secrets_policy" {
  name        = "careerai-${var.environment}-ecs-secrets-policy"
  description = "Allows ECS tasks to read CareerAI application secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [aws_secretsmanager_secret.app_secrets.arn]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_secrets_attach" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = aws_iam_policy.ecs_secrets_policy.arn
}

# -----------------------------------------------------------------------------
# ECS Task Role (Runtime permissions for the running Python application)
# -----------------------------------------------------------------------------
resource "aws_iam_role" "ecs_task_role" {
  name = "careerai-${var.environment}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "ecs-tasks.amazonaws.com" }
      }
    ]
  })
}

# Grant access to S3 documents bucket only (least privilege)
resource "aws_iam_policy" "ecs_s3_documents_policy" {
  name        = "careerai-${var.environment}-ecs-s3-documents"
  description = "Allows CareerAI application to perform Get/Put/Delete on documents S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:HeadObject"
        ]
        Resource = ["${aws_s3_bucket.documents.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = [
          "s3:ListBucket"
        ]
        Resource = [aws_s3_bucket.documents.arn]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_s3_attach" {
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = aws_iam_policy.ecs_s3_documents_policy.arn
}
