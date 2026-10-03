# ==============================================================================
# Prosigliere Analytics Engineering - Infrastructure Variables
# ==============================================================================

variable "aws_region" {
  type        = string
  description = "AWS region for analytical infrastructure deployment"
  default     = "us-east-1"
}

variable "environment" {
  type        = string
  description = "Deployment lifecycle stage (production, staging, test)"
  default     = "production"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the dedicated analytical lakehouse VPC"
  default     = "10.40.0.0/16"
}

variable "db_instance_class" {
  type        = string
  description = "Compute instance size for PostgreSQL 16 analytical lakehouse"
  default     = "db.r6g.xlarge"
}
