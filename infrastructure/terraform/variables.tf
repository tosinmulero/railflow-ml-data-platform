variable "aws_region" {
  description = "AWS region used for the RailFlow platform."
  type        = string
  default     = "eu-west-2"
}

variable "project_name" {
  description = "RailFlow project identifier."
  type        = string
  default     = "railflow"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"

  validation {
    condition = contains(
      ["dev", "staging", "prod"],
      var.environment
    )

    error_message = "environment must be dev, staging, or prod."
  }
}

variable "vpc_cidr" {
  description = "CIDR range for the RailFlow VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "container_port" {
  description = "RailFlow FastAPI container port."
  type        = number
  default     = 8000
}

variable "health_check_path" {
  description = "RailFlow ALB health-check endpoint."
  type        = string
  default     = "/health"
}

variable "log_retention_days" {
  description = "CloudWatch ECS log retention."
  type        = number
  default     = 14
}

variable "ecr_force_delete" {
  description = "Allow Terraform to delete a non-empty dev ECR repository."
  type        = bool
  default     = false
}

variable "alb_deletion_protection" {
  description = "Enable ALB deletion protection."
  type        = bool
  default     = false
}

variable "extra_tags" {
  description = "Additional tags applied to AWS resources."
  type        = map(string)
  default     = {}
}