output "ecs_service_name" {
  description = "RailFlow ECS service name."
  value       = aws_ecs_service.railflow_api.name
}

output "ecs_task_definition_family" {
  description = "RailFlow ECS task definition family."
  value       = aws_ecs_task_definition.railflow_api.family
}

output "ecs_task_definition_arn" {
  description = "RailFlow ECS task definition ARN."
  value       = aws_ecs_task_definition.railflow_api.arn
}

output "ecs_container_name" {
  description = "RailFlow ECS container name."
  value       = local.railflow_container_name
}

output "configured_container_image" {
  description = "Container image configured in the Terraform task definition."
  value       = local.railflow_container_image
}

output "github_deploy_role_arn" {
  description = "GitHub Actions AWS deployment role ARN."
  value       = aws_iam_role.github_deploy.arn
}

output "github_oidc_provider_arn" {
  description = "GitHub Actions OIDC provider ARN."
  value       = aws_iam_openid_connect_provider.github.arn
}