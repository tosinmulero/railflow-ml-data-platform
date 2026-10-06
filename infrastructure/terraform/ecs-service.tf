locals {
  railflow_container_name = "railflow-api"

  railflow_container_image = "${aws_ecr_repository.railflow.repository_url}:${var.container_image_tag}"
}

resource "aws_ecs_task_definition" "railflow_api" {
  family = "${local.name_prefix}-api"

  requires_compatibilities = [
    "FARGATE"
  ]

  network_mode = "awsvpc"

  cpu    = tostring(var.task_cpu)
  memory = tostring(var.task_memory)

  execution_role_arn = aws_iam_role.ecs_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name      = local.railflow_container_name
      image     = local.railflow_container_image
      essential = true

      portMappings = [
        {
          name          = "http"
          containerPort = var.container_port
          hostPort      = var.container_port
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "RAILFLOW_ENVIRONMENT"
          value = var.environment
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group         = aws_cloudwatch_log_group.railflow_api.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "railflow-api"
        }
      }

      healthCheck = {
        command = [
          "CMD-SHELL",
          "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)\" || exit 1"
        ]

        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }
    }
  ])

  tags = {
    Name = "${local.name_prefix}-api-task"
  }
}

resource "aws_ecs_service" "railflow_api" {
  name = "${local.name_prefix}-api-service"

  cluster         = aws_ecs_cluster.railflow.id
  task_definition = aws_ecs_task_definition.railflow_api.arn

  desired_count = var.service_desired_count

  platform_version = "LATEST"

  health_check_grace_period_seconds = var.deployment_health_check_grace_period_seconds

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  capacity_provider_strategy {
    capacity_provider = "FARGATE"
    base              = 1
    weight            = 1
  }

  network_configuration {
    subnets = aws_subnet.public[*].id

    security_groups = [
      aws_security_group.ecs.id
    ]

    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.railflow_api.arn

    container_name = local.railflow_container_name
    container_port = var.container_port
  }

  depends_on = [
    aws_lb_listener.http,
    aws_iam_role_policy_attachment.ecs_execution,
    aws_ecs_cluster_capacity_providers.railflow
  ]

  tags = {
    Name = "${local.name_prefix}-api-service"
  }
}