variable "container_image_tag" {
  description = "ECR image tag used by the ECS task definition."
  type        = string
  default     = "bootstrap"
}

variable "task_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 512

  validation {
    condition = contains(
      [256, 512, 1024, 2048, 4096],
      var.task_cpu
    )

    error_message = "task_cpu must be a supported Fargate CPU value."
  }
}

variable "task_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 1024
}

variable "service_desired_count" {
  description = "Initial ECS service desired task count."
  type        = number
  default     = 0

  validation {
    condition     = var.service_desired_count >= 0
    error_message = "service_desired_count cannot be negative."
  }
}

variable "deployment_health_check_grace_period_seconds" {
  description = "Grace period before ALB health checks affect ECS deployments."
  type        = number
  default     = 90
}

variable "github_repository" {
  description = "GitHub repository allowed to assume the AWS deployment role."
  type        = string
  default     = "tosinmulero/railflow-ml-data-platform"
}