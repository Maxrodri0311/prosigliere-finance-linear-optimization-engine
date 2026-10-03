# ==============================================================================
# Prosigliere Analytics Engineering - RDS PostgreSQL 16 Lakehouse Provisioning
# Target Engine : PostgreSQL 16.2 / Multi-AZ Analytical Cluster
# Configuration : Optimized for Vectorized Ingestion, Partition Scans & BRIN Indexing
# ==============================================================================

resource "aws_db_subnet_group" "lakehouse_subnet_group" {
  name        = "prosigliere-lakehouse-db-subnet-group"
  description = "Private DB subnet group for PostgreSQL 16 analytical lakehouse"
  subnet_ids  = [
    aws_subnet.private_lakehouse_subnet_a.id,
    aws_subnet.private_lakehouse_subnet_b.id
  ]

  tags = {
    Name = "prosigliere-lakehouse-db-subnet-group"
  }
}

resource "aws_db_parameter_group" "pg16_analytical_params" {
  name        = "prosigliere-pg16-analytical-params"
  family      = "postgres16"
  description = "PostgreSQL 16 parameter group tuned for OLAP window queries and BRIN scans"

  parameter {
    name  = "work_mem"
    value = "65536" # 64MB for in-memory window sort and hash aggregates
  }

  parameter {
    name  = "maintenance_work_mem"
    value = "524288" # 512MB for high-speed BRIN index construction
  }

  parameter {
    name  = "max_parallel_workers_per_gather"
    value = "4" # Parallel worker scans for partitioned tables
  }

  parameter {
    name  = "random_page_cost"
    value = "1.1" # Fast NVMe SSD storage access assumption
  }

  parameter {
    name  = "effective_cache_size"
    value = "1572864" # 12GB effective OS cache estimate
  }

  parameter {
    name  = "statement_timeout"
    value = "60000" # 60 seconds SLA ceiling to prevent runaway queries
  }

  tags = {
    Name = "prosigliere-pg16-analytical-params"
  }
}

resource "aws_db_instance" "lakehouse_postgres" {
  identifier                  = "prosigliere-marketing-lakehouse-pg16"
  engine                      = "postgres"
  engine_version              = "16.2"
  instance_class              = var.db_instance_class
  allocated_storage           = 100
  max_allocated_storage       = 500
  storage_type                = "gp3"
  storage_encrypted           = true
  kms_key_id                  = aws_kms_key.marketing_data_key.arn
  multi_az                    = var.environment == "production" ? true : false

  db_name                     = "prosigliere_lakehouse"
  username                    = "lakehouse_admin"
  manage_master_user_password = true

  db_subnet_group_name        = aws_db_subnet_group.lakehouse_subnet_group.name
  vpc_security_group_ids      = [aws_security_group.rds_postgres_sg.id]
  parameter_group_name        = aws_db_parameter_group.pg16_analytical_params.name

  backup_retention_period     = 14
  backup_window               = "03:00-04:00"
  maintenance_window          = "Sun:04:30-Sun:05:30"
  auto_minor_version_upgrade  = true
  copy_tags_to_snapshot       = true
  deletion_protection         = var.environment == "production" ? true : false
  skip_final_snapshot         = var.environment == "production" ? false : true
  final_snapshot_identifier   = "prosigliere-lakehouse-final-snapshot"

  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  performance_insights_kms_key_id       = aws_kms_key.marketing_data_key.arn

  tags = {
    Name        = "prosigliere-marketing-lakehouse-pg16"
    Role        = "Analytics-OLAP-Storage"
    Environment = var.environment
  }
}
