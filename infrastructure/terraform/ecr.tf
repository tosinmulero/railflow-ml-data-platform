resource "aws_ecr_repository" "railflow" {
  name = local.name_prefix

  image_tag_mutability = "IMMUTABLE"

  force_delete = var.ecr_force_delete

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "${local.name_prefix}-ecr"
  }
}

resource "aws_ecr_lifecycle_policy" "railflow" {
  repository = aws_ecr_repository.railflow.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Remove untagged images after one day"

        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }

        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep the latest 20 tagged images"

        selection = {
          tagStatus      = "tagged"
          tagPatternList = [
            "*"
          ]
          countType   = "imageCountMoreThan"
          countNumber = 20
        }

        action = {
          type = "expire"
        }
      }
    ]
  })
}