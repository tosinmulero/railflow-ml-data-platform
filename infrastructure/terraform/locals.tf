locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = merge(
    {
      Project     = "RailFlow ML Data Platform"
      Application = "railflow-api"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Repository  = "tosinmulero/railflow-ml-data-platform"
    },
    var.extra_tags
  )

  public_subnet_cidrs = [
    cidrsubnet(var.vpc_cidr, 8, 0),
    cidrsubnet(var.vpc_cidr, 8, 1)
  ]
}