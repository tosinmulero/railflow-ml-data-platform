# RailFlow Architecture

## Data Layers

### Bronze
Immutable representation of ingested source data.

### Silver
Cleaned, standardised and validated datasets.

### Gold
Business-facing data marts and machine-learning-ready datasets.

## ML Data Flow

Source Data
→ Ingestion
→ Bronze
→ Spark
→ Silver
→ dbt
→ Gold
→ Feature Engineering
→ Feature Store
→ Training
→ Evaluation
→ Registry
→ Inference

## Production Engineering

The platform will eventually include:

- Airflow orchestration
- Spark distributed processing
- dbt transformations
- Parquet and Iceberg storage
- MLflow experiment tracking
- Docker
- Terraform
- AWS
- GitHub Actions CI/CD
- Automated testing
- Data quality checks
- Pipeline observability
