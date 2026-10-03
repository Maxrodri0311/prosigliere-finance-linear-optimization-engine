# ==============================================================================
# Prosigliere Analytics Engineering - Security, Encryption & IAM Governance (IaC)
# Target Service: AWS KMS, IAM Roles & Least-Privilege Policies
# Standard      : SOC2 Type II Compliant Customer-Managed Encryption
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. Dedicated Customer-Managed KMS Key for Marketing & Financial Telemetry
# ------------------------------------------------------------------------------
resource "aws_kms_key" "marketing_data_key" {
  description             = "KMS Key for Prosigliere marketing telemetry and RDS lakehouse encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableIAMUserPermissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowRDSAndS3Encryption"
        Effect = "Allow"
        Principal = {
          Service = [
            "rds.amazonaws.com",
            "s3.amazonaws.com"
          ]
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name = "prosigliere-marketing-cmk"
  }
}

resource "aws_kms_alias" "marketing_data_key_alias" {
  name          = "alias/prosigliere-marketing-key"
  target_key_id = aws_kms_key.marketing_data_key.key_id
}

data "aws_caller_identity" "current" {}

# ------------------------------------------------------------------------------
# 2. Least-Privilege IAM Execution Role for Analytics & dbt Pipelines
# ------------------------------------------------------------------------------
resource "aws_iam_role" "analytics_execution_role" {
  name = "prosigliere-analytics-execution-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = [
            "ecs-tasks.amazonaws.com",
            "lambda.amazonaws.com"
          ]
        }
      }
    ]
  })

  tags = {
    Name = "prosigliere-analytics-execution-role"
  }
}

resource "aws_iam_policy" "lakehouse_read_write_policy" {
  name        = "prosigliere-lakehouse-rw-policy"
  description = "Allows analytics worker to read/write S3 telemetry and invoke KMS encryption"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3LakehouseAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:AbortMultipartUpload"
        ]
        Resource = [
          aws_s3_bucket.telemetry_lake.arn,
          "${aws_s3_bucket.telemetry_lake.arn}/*"
        ]
      },
      {
        Sid    = "KMSEncryptionAccess"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = [
          aws_kms_key.marketing_data_key.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_lakehouse_policy" {
  role       = aws_iam_role.analytics_execution_role.name
  policy_arn = aws_iam_policy.lakehouse_read_write_policy.arn
}
