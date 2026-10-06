output "aws_region" {
  description = "AWS region."
  value       = var.aws_region
}

output "vpc_id" {
  description = "RailFlow VPC ID."
  value       = aws_vpc.railflow.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs."
  value       = aws_subnet.public[*].id
}

output "alb_dns_name" {
  description = "RailFlow ALB DNS endpoint."
  value       = aws_lb.railflow.dns_name
}

output "alb_arn" {
  description = "RailFlow ALB ARN."
  value       = aws_lb.railflow.arn
}

output "target_group_arn" {
  description = "RailFlow API target group ARN."
  value       = aws_lb_target_group.railflow_api.arn
}

output "ecs_cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.railflow.name
}

output "ecs_cluster_arn" {
  description = "ECS cluster ARN."
  value       = aws_ecs_cluster.railflow.arn
}

output "ecs_security_group_id" {
  description = "RailFlow ECS security group."
  value       = aws_security_group.ecs.id
}

output "ecr_repository_name" {
  description = "RailFlow ECR repository name."
  value       = aws_ecr_repository.railflow.name
}

output "ecr_repository_url" {
  description = "RailFlow ECR repository URL."
  value       = aws_ecr_repository.railflow.repository_url
}

output "ecs_execution_role_arn" {
  description = "ECS task execution role ARN."
  value       = aws_iam_role.ecs_execution.arn
}

output "ecs_task_role_arn" {
  description = "RailFlow ECS task role ARN."
  value       = aws_iam_role.ecs_task.arn
}

output "cloudwatch_log_group" {
  description = "RailFlow API CloudWatch log group."
  value       = aws_cloudwatch_log_group.railflow_api.name
}