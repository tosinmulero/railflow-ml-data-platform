# RailFlow AWS Infrastructure

Terraform infrastructure for the RailFlow ML Data Platform.

## Stage 9A

The foundation defines:

- AWS VPC
- Two public subnets across separate Availability Zones
- Internet Gateway
- Public route table
- Application Load Balancer
- ALB target group with `/health` checks
- ALB and ECS security groups
- Amazon ECR repository
- Amazon ECS cluster
- Fargate and Fargate Spot capacity providers
- CloudWatch Logs
- ECS task execution IAM role
- ECS application task IAM role
- Standard RailFlow tagging

## Deployment model

Traffic flow:

Internet
→ Application Load Balancer
→ ECS security group
→ ECS Fargate task
→ RailFlow FastAPI container on port 8000

Only the ALB security group is permitted to reach the application port.

## Region

Default AWS region:

`eu-west-2`

## Important

Stage 9A validates the infrastructure definition only.

Do not run `terraform apply` until Stage 9B deployment configuration and AWS authentication are ready.