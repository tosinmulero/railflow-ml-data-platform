# RailFlow Platform Architecture

RailFlow is a production-style data and ML engineering portfolio platform built around UK rail station usage data.

## Data Path

```text
ORR source
  -> Raw
  -> Bronze
  -> Silver
  -> Gold
  -> dbt analytics
  -> ML feature store
```

## ML Path

```text
Feature store
  -> candidate training
  -> MLflow experiment tracking
  -> champion model registry
  -> validated skops serving artifact
  -> FastAPI
  -> Docker
  -> ECR
  -> ECS/Fargate
  -> ALB
```

## Orchestration

Apache Airflow manages the data pipeline and a separate ML lifecycle DAG.

## Cloud Deployment

Terraform provisions AWS networking, ECR, ECS/Fargate, ALB, CloudWatch and IAM. GitHub Actions authenticates to AWS with OIDC, builds an immutable Docker image and deploys it to ECS.

## Security Boundaries

- Only the ALB is internet-facing.
- ECS ingress is restricted to the ALB security group.
- The application container runs as a non-root user.
- GitHub deployment uses OIDC instead of storing AWS deployment keys.
- The OIDC trust policy is restricted to the immutable repository identity and main branch.
- The model artifact is validated before serving.
- API inputs are validated with Pydantic.

## Deployment Philosophy

The AWS environment is an ephemeral development/portfolio deployment. It can be destroyed after evidence capture to prevent unnecessary recurring cloud cost while leaving the full deployment reproducible from Terraform and GitHub Actions.
