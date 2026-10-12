# DB Subnet Group spanning the private database subnets
resource "aws_db_subnet_group" "rds" {
  name        = "careerai-${var.environment}-db-subnet-group"
  description = "Subnet group for private CareerAI RDS MySQL cluster"
  subnet_ids  = aws_subnet.database[*].id

  tags = {
    Name = "careerai-${var.environment}-db-subnet-group"
  }
}

resource "random_password" "db_password" {
  length           = 32
  special          = false
}

# Parameter group enforcing UTF-8 mb4 for multilingual job descriptions and resumes
resource "aws_db_parameter_group" "mysql" {
  name   = "careerai-${var.environment}-mysql8-params"
  family = "mysql8.0"

  parameter {
    name  = "character_set_server"
    value = "utf8mb4"
  }

  parameter {
    name  = "collation_server"
    value = "utf8mb4_unicode_ci"
  }

  parameter {
    name  = "max_connections"
    value = "200"
  }
}

resource "aws_db_instance" "mysql" {
  identifier             = "careerai-${var.environment}-mysql"
  engine                 = "mysql"
  engine_version         = "8.0"
  instance_class         = var.db_instance_class
  allocated_storage      = var.db_allocated_storage
  max_allocated_storage  = 100
  storage_type           = "gp3"
  storage_encrypted      = true

  db_name                = "careerai_db"
  username               = "careerai_admin"
  password               = random_password.db_password.result

  db_subnet_group_name   = aws_db_subnet_group.rds.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.mysql.name

  multi_az               = var.environment == "production" ? true : false
  publicly_accessible    = false
  skip_final_snapshot    = var.environment == "production" ? false : true
  final_snapshot_identifier = "careerai-${var.environment}-mysql-final"

  backup_retention_period   = 7
  backup_window             = "03:00-04:00"
  maintenance_window        = "sun:04:30-sun:05:30"
  auto_minor_version_upgrade = true
  deletion_protection       = var.environment == "production" ? true : false

  tags = {
    Name = "careerai-${var.environment}-mysql"
  }
}
