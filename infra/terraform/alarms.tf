# -----------------------------------------------------------------------------
# CloudWatch Alarm: High 5xx HTTP Error Rate on ALB
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "alb_5xx_errors" {
  alarm_name          = "careerai-${var.environment}-high-5xx-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "Triggered when API target group generates >10 5xx responses in a 1-minute interval"

  dimensions = {
    TargetGroup  = aws_lb_target_group.api.arn_suffix
    LoadBalancer = aws_lb.main.arn_suffix
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Alarm: High Latency (>500ms target response time)
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "alb_latency" {
  alarm_name          = "careerai-${var.environment}-high-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Average"
  threshold           = 0.5
  alarm_description   = "Triggered when average target response time exceeds 500ms for 3 consecutive minutes"

  dimensions = {
    TargetGroup  = aws_lb_target_group.api.arn_suffix
    LoadBalancer = aws_lb.main.arn_suffix
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Alarm: High RDS Database CPU (>80%)
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "rds_high_cpu" {
  alarm_name          = "careerai-${var.environment}-rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Triggered when RDS MySQL instance CPU exceeds 80% for 10 minutes"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.mysql.id
  }
}
