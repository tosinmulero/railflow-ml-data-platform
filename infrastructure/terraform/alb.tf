resource "aws_lb" "railflow" {
  name = "${local.name_prefix}-alb"

  internal           = false
  load_balancer_type = "application"

  security_groups = [
    aws_security_group.alb.id
  ]

  subnets = aws_subnet.public[*].id

  enable_deletion_protection = var.alb_deletion_protection

  tags = {
    Name = "${local.name_prefix}-alb"
  }
}

resource "aws_lb_target_group" "railflow_api" {
  name = "${local.name_prefix}-api-tg"

  port        = var.container_port
  protocol    = "HTTP"
  target_type = "ip"

  vpc_id = aws_vpc.railflow.id

  health_check {
    enabled = true

    path = var.health_check_path

    protocol = "HTTP"

    matcher = "200-399"

    interval = 30
    timeout  = 5

    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = {
    Name = "${local.name_prefix}-api-tg"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.railflow.arn

  port     = 80
  protocol = "HTTP"

  default_action {
    type = "forward"

    target_group_arn = aws_lb_target_group.railflow_api.arn
  }
}