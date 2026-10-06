# RailFlow AWS Infrastructure

Terraform infrastructure for the RailFlow ML Data Platform.

## Architecture

RailFlow uses:

- Amazon VPC
- Two public subnets across separate Availability Zones
- Internet Gateway
- Application Load Balancer
- ECS Fargate
- Amazon ECR
- CloudWatch Logs
- IAM least-privilege roles
- GitHub Actions OIDC authentication

## Traffic flow

Internet
→ Application Load Balancer
→ ECS security group
→ ECS Fargate service
→ RailFlow FastAPI container
→ `/health`, `/model`, `/predict`

The ECS application port is not directly open to the internet.

Only the ALB security group can reach port 8000 on the ECS tasks.

## Container deployment

Terraform creates the ECR repository, ECS cluster, task definition, service,
load balancer, logging, IAM roles, and GitHub OIDC deployment role.

The service begins with:

`service_desired_count = 0`

This prevents ECS from attempting to pull a bootstrap image before the first
real RailFlow image has been pushed to ECR.

The manual GitHub workflow:

`.github/workflows/aws-ecs-deploy.yml`

performs:

1. GitHub OIDC authentication to AWS
2. Docker build
3. Push immutable `sha-<commit>` image to ECR
4. Download the current ECS task definition
5. Insert the new image URI
6. Register the task definition revision
7. Update the ECS service
8. Scale the service to one task
9. Wait for ECS service stability
10. Verify running task count

No long-lived AWS access keys are stored in GitHub.

## AWS Region

Default region:

`eu-west-2`

## Deployment safety

Terraform validation does not create AWS resources.

Actual AWS provisioning requires an explicit:

`terraform apply`

The AWS ECS deployment workflow is manual-only and cannot deploy until the
Terraform infrastructure exists and the repository variable
`AWS_DEPLOY_ROLE_ARN` has been configured.