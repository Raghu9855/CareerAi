# -----------------------------------------------------------------------------
# ALB Security Group: Ingress 80/443 from Internet, Egress to ECS only
# -----------------------------------------------------------------------------
resource "aws_security_group" "alb" {
  name        = "careerai-${var.environment}-alb-sg"
  description = "Allows incoming HTTP/HTTPS traffic to Application Load Balancer"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "Allow HTTP from internet (redirects to HTTPS)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Allow HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description     = "Allow traffic to ECS tasks on application port 8000 only"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  tags = {
    Name = "careerai-${var.environment}-alb-sg"
  }
}

# -----------------------------------------------------------------------------
# ECS Tasks Security Group: Ingress from ALB only, Egress to RDS & HTTPS
# -----------------------------------------------------------------------------
resource "aws_security_group" "ecs" {
  name        = "careerai-${var.environment}-ecs-sg"
  description = "Allows ingress from ALB and egress to RDS & external APIs"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Allow incoming requests from ALB on port 8000"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "Allow HTTPS outbound for AWS APIs, ECR, Secrets Manager, and LLMs"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description     = "Allow outbound connection to RDS MySQL"
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.rds.id]
  }

  tags = {
    Name = "careerai-${var.environment}-ecs-sg"
  }
}

# -----------------------------------------------------------------------------
# RDS MySQL Security Group: Ingress on 3306 exclusively from ECS tasks
# -----------------------------------------------------------------------------
resource "aws_security_group" "rds" {
  name        = "careerai-${var.environment}-rds-sg"
  description = "Allows MySQL ingress exclusively from ECS tasks"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Allow MySQL traffic from ECS security group only"
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  egress {
    description = "No outbound egress required for database"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "careerai-${var.environment}-rds-sg"
  }
}
