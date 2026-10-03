# ==============================================================================
# Prosigliere Analytics Engineering - Infrastructure Output Specifications
# ==============================================================================

output "vpc_id" {
  description = "Identifier of the dedicated analytical lakehouse VPC"
  value       = aws_vpc.analytical_vpc.id
}

output "public_subnet_ids" {
  description = "List of public DMZ subnets for analytical gateways"
  value       = [aws_subnet.public_subnet_a.id, aws_subnet.public_subnet_b.id]
}

output "private_lakehouse_subnet_ids" {
  description = "List of private subnets hosting RDS PostgreSQL and analytical workers"
  value       = [aws_subnet.private_lakehouse_subnet_a.id, aws_subnet.private_lakehouse_subnet_b.id]
}

output "s3_telemetry_lake_bucket_name" {
  description = "Name of the append-only S3 marketing telemetry data lake"
  value       = aws_s3_bucket.telemetry_lake.id
}

output "s3_telemetry_lake_arn" {
  description = "Amazon Resource Name (ARN) of the telemetry lake bucket"
  value       = aws_s3_bucket.telemetry_lake.arn
}

output "rds_postgres_endpoint" {
  description = "Connection endpoint hostname for PostgreSQL 16 analytical lakehouse"
  value       = aws_db_instance.lakehouse_postgres.endpoint
}

output "rds_postgres_port" {
  description = "TCP listening port for PostgreSQL 16 connection"
  value       = aws_db_instance.lakehouse_postgres.port
}

output "rds_postgres_database_name" {
  description = "Default database name for analytical operations"
  value       = aws_db_instance.lakehouse_postgres.db_name
}

output "kms_key_arn" {
  description = "ARN of Customer Managed KMS Key encrypting telemetry and RDS storage"
  value       = aws_kms_key.marketing_data_key.arn
}

output "analytics_execution_role_arn" {
  description = "IAM Role ARN assumed by automated analytics and dbt pipelines"
  value       = aws_iam_role.analytics_execution_role.arn
}