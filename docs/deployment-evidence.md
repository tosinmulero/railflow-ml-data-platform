# AWS Deployment Evidence

## Environment

- Region: eu-west-2
- Runtime: Amazon ECS on AWS Fargate
- Registry: Amazon ECR
- Ingress: Application Load Balancer
- Logging: CloudWatch
- Infrastructure as Code: Terraform
- CI/CD: GitHub Actions
- AWS authentication: GitHub OIDC

## Terraform Foundation

```text
Plan: 25 to add, 0 to change, 0 to destroy.
```

## Successful Deployment

GitHub Actions deployment run:

```text
37551332811
```

The successful workflow completed:

```text
Configure AWS credentials with GitHub OIDC
Verify AWS identity
Login to Amazon ECR
Build and push immutable RailFlow image
Download current ECS task definition
Render task definition
Deploy task definition to ECS
Activate RailFlow service
Verify ECS service state
```

## ECS Verification

```text
Status  : ACTIVE
Desired : 1
Running : 1
Pending : 0
```

## API Verification

### /health

```json
{
  "status": "ok",
  "model_loaded": true,
  "model_name": "railflow_station_interchange_regressor",
  "model_alias": "champion"
}
```

### /model

```text
registered_model_name = railflow_station_interchange_regressor
alias                 = champion
version               = 1
validation_status     = approved
target                = c6
```

### /predict

```text
predicted_annual_interchanges = 3.753798096083773
rounded                       = 4
model_version                 = 1
model_alias                   = champion
```

## Cost Control

The live environment is intentionally temporary. After portfolio evidence is captured, Terraform can destroy the billable infrastructure while preserving the full reproducible implementation in source control.
