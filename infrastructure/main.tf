# ==============================================================================
# Prosigliere Analytics Engineering - Modern Data Lakehouse Infrastructure (IaC)
# Target Provider: AWS (S3 Data Lake, VPC, Security Groups, IAM & RDS PostgreSQL)
# Role           : Analytics Engineer
# Architecture   : Dual-Tier Secure VPC, Append-Only S3 Lake & Encrypted RDS OLAP
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Organization = "Prosigliere"
      Environment  = var.environment
      ManagedBy    = "Terraform"
      Repository   = "prosigliere-finance-linear-optimization-engine"
      TargetRole   = "Analytics Engineer"
      Compliance   = "SOC2-Type-II"
    }
  }
}

# ------------------------------------------------------------------------------
# 1. Dual-Subnet High-Availability VPC for Analytical Data Pipelines
# ------------------------------------------------------------------------------
resource "aws_vpc" "analytical_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "prosigliere-marketing-analytics-vpc"
  }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.analytical_vpc.id

  tags = {
    Name = "prosigliere-analytics-igw"
  }
}

resource "aws_subnet" "public_subnet_a" {
  vpc_id                  = aws_vpc.analytical_vpc.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, 0)
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "prosigliere-analytics-public-a"
    Tier = "DMZ"
  }
}

resource "aws_subnet" "public_subnet_b" {
  vpc_id                  = aws_vpc.analytical_vpc.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, 1)
  availability_zone       = "${var.aws_region}b"
  map_public_ip_on_launch = true

  tags = {
    Name = "prosigliere-analytics-public-b"
    Tier = "DMZ"
  }
}

resource "aws_subnet" "private_lakehouse_subnet_a" {
  vpc_id            = aws_vpc.analytical_vpc.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, 2)
  availability_zone = "${var.aws_region}a"

  tags = {
    Name = "prosigliere-lakehouse-private-a"
    Tier = "DataLake"
  }
}

resource "aws_subnet" "private_lakehouse_subnet_b" {
  vpc_id            = aws_vpc.analytical_vpc.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, 3)
  availability_zone = "${var.aws_region}b"

  tags = {
    Name = "prosigliere-lakehouse-private-b"
    Tier = "DataLake"
  }
}

# ------------------------------------------------------------------------------
# 2. Production S3 Marketing Telemetry & Reverse ETL Data Lake
# ------------------------------------------------------------------------------
resource "aws_s3_bucket" "telemetry_lake" {
  bucket        = "prosigliere-marketing-analytics-lake-${var.environment}"
  force_destroy = false

  tags = {
    Name        = "prosigliere-marketing-analytics-lake"
    DataClass   = "Confidential-Marketing-Telemetry"
  }
}

resource "aws_s3_bucket_versioning" "telemetry_versioning" {
  bucket = aws_s3_bucket.telemetry_lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "telemetry_crypto" {
  bucket = aws_s3_bucket.telemetry_lake.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.marketing_data_key.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "block_public_lake" {
  bucket = aws_s3_bucket.telemetry_lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "telemetry_lifecycle" {
  bucket = aws_s3_bucket.telemetry_lake.id

  rule {
    id     = "archive-parquet-partitions-to-glacier"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}

# ------------------------------------------------------------------------------
# 3. Security Groups: Zero-Trust Strict Isolation
# ------------------------------------------------------------------------------
resource "aws_security_group" "rds_postgres_sg" {
  name        = "prosigliere-rds-postgres-sg"
  description = "Controls inbound traffic to PostgreSQL 16 analytical lakehouse"
  vpc_id      = aws_vpc.analytical_vpc.id

  ingress {
    description = "PostgreSQL access from ECS Analytical Worker"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    security_groups = [aws_security_group.analytical_worker_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "prosigliere-rds-postgres-sg"
  }
}

resource "aws_security_group" "analytical_worker_sg" {
  name        = "prosigliere-analytical-worker-sg"
  description = "Security group for FastAPI inference and dbt transformation worker"
  vpc_id      = aws_vpc.analytical_vpc.id

  ingress {
    description = "HTTPS API ingress"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "FastAPI uvicorn port"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "prosigliere-analytical-worker-sg"
  }
}