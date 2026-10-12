resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "documents" {
  bucket        = "careerai-${var.environment}-documents-${random_id.bucket_suffix.hex}"
  force_destroy = false

  tags = {
    Name        = "careerai-${var.environment}-documents"
    Purpose     = "Private Career Document & Resume Storage"
    Sensitivity = "Confidential"
  }
}

# Enforce Server-Side Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "docs_encryption" {
  bucket = aws_s3_bucket.documents.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block all Public Access (100% Private)
resource "aws_s3_bucket_public_access_block" "docs_public_block" {
  bucket = aws_s3_bucket.documents.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable Object Versioning for Disaster Recovery
resource "aws_s3_bucket_versioning" "docs_versioning" {
  bucket = aws_s3_bucket.documents.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Lifecycle management: abort incomplete uploads and archive old versions
resource "aws_s3_bucket_lifecycle_configuration" "docs_lifecycle" {
  bucket = aws_s3_bucket.documents.id

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}
