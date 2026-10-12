# CareerAI AWS Deployment & Infrastructure Guide

This guide details the complete, reproducible process for deploying **CareerAI** to Amazon Web Services (AWS) using Terraform, Amazon ECS (Fargate), RDS MySQL, S3, Secrets Manager, and Application Load Balancer with HTTPS.

---

## 1. Architectural Overview

```
                      Internet
                         │
                         ▼
             [Route 53 / DNS HTTPS:443]
                         │
                         ▼
         [Application Load Balancer (Public Subnets)]
                 │                       │
      (HTTP:80 -> Redirect HTTPS)        │ Forward :8000
                                         ▼
            [AWS ECS Fargate Tasks (Private Subnets)]
            ├── Container: careerai-api:latest
            ├── Execution Role: Pull ECR, CloudWatch Logs, Secrets
            └── Task Role: S3 Get/Put/Delete (Least Privilege)
                 │                       │
         Private VPC Peering      Private DB Subnets
                 │                       │
                 ▼                       ▼
       [Amazon S3 Documents]   [Amazon RDS MySQL 8.0]
     (AES-256, 100% Private)   (Encrypted, Multi-AZ)
```

---

## 2. Prerequisites

1. **AWS CLI v2** configured with administrative credentials (`aws configure`).
2. **Terraform** >= 1.5.0 installed.
3. **Docker** and Buildx installed locally for image builds.
4. An **ACM Certificate ARN** for your domain (e.g. `arn:aws:acm:us-east-1:123456789012:certificate/...`).

> [!CAUTION]
> Terraform commands provision billable AWS resources (RDS, NAT Gateway, ALB, Fargate). Always verify estimated costs and review plans prior to `terraform apply`.

---

## 3. Step-by-Step Provisioning

### Step 3.1: Initialize Terraform
Navigate to the Terraform directory:
```bash
cd infra/terraform
terraform init
```

### Step 3.2: Configure Variables
Create a `terraform.tfvars` file (do **NOT** commit to git):
```hcl
aws_region           = "us-east-1"
environment          = "production"
vpc_cidr             = "10.0.0.0/16"
domain_name          = "api.careerai.io"
certificate_arn      = "arn:aws:acm:us-east-1:123456789012:certificate/your-cert-id"
db_instance_class    = "db.t4g.small"
db_allocated_storage = 20
container_cpu        = 512
container_memory     = 1024
desired_count        = 2
```

### Step 3.3: Plan & Apply Infrastructure
```bash
terraform plan -out=tfplan
terraform apply tfplan
```
Once complete, Terraform will output:
- `alb_dns_name`: Load Balancer address
- `ecr_repository_url`: ECR image repository URI
- `rds_endpoint`: Private database endpoint
- `s3_bucket_name`: Secure S3 bucket ID
- `secrets_manager_arn`: ARN of application secrets

---

## 4. Populating Production Secrets

Update the secret payload in AWS Secrets Manager:
```bash
aws secretsmanager put-secret-value \
  --secret-id "careerai/production/app-secrets" \
  --secret-string '{
    "SECRET_KEY": "'$(openssl rand -hex 32)'",
    "DATABASE_URL": "mysql+asyncmy://careerai_admin:<DB_PASSWORD>@<RDS_ENDPOINT>/careerai_db",
    "OPENAI_API_KEY": "sk-proj-...",
    "S3_BUCKET_NAME": "<S3_BUCKET_NAME>",
    "AWS_REGION": "us-east-1",
    "STORAGE_BACKEND": "s3",
    "LLM_PROVIDER": "openai",
    "VECTOR_STORE_TYPE": "memory"
  }'
```

---

## 5. Build, Tag & Push Docker Image

Authenticate Docker with Amazon ECR:
```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <ECR_REPOSITORY_URL>
```

Build and push the multi-stage image:
```bash
docker build -t careerai-api:latest -f docker/Dockerfile .
docker tag careerai-api:latest <ECR_REPOSITORY_URL>:latest
docker tag careerai-api:latest <ECR_REPOSITORY_URL>:sha-$(git rev-parse --short HEAD)

docker push <ECR_REPOSITORY_URL>:latest
docker push <ECR_REPOSITORY_URL>:sha-$(git rev-parse --short HEAD)
```

---

## 6. Safe Pre-Deployment Database Migrations

Before triggering a rolling update of the API tasks, run the Alembic database migrations as a standalone ECS Fargate task:

```bash
aws ecs run-task \
  --cluster careerai-production-cluster \
  --task-definition careerai-production-api \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[<PRIVATE_SUBNET_1>],securityGroups=[<ECS_SG_ID>],assignPublicIp=DISABLED}" \
  --overrides '{
    "containerOverrides": [
      {
        "name": "api",
        "command": ["python", "scripts/run_migrations_ecs.py"]
      }
    ]
  }'
```

Monitor task exit code:
```bash
aws ecs wait tasks-stopped --cluster careerai-production-cluster --tasks <TASK_ARN>
```

---

## 7. Zero-Downtime Rolling Deployment

Trigger a rolling deployment on the ECS service:
```bash
aws ecs update-service \
  --cluster careerai-production-cluster \
  --service careerai-production-service \
  --force-new-deployment
```

### Deployment Strategy Parameters:
- `minimum_healthy_percent`: `100` (Guarantees that active tasks are not terminated until new tasks have passed ALB healthchecks).
- `maximum_percent`: `200` (Allows Fargate to spawn 2x instances while shifting traffic).
- Healthcheck interval: 15 seconds against `GET /health`.

---

## 8. Rollback Runbook

If CloudWatch Alarms trigger high latency or 5xx errors during deployment:

### Instant Task Definition Rollback:
```bash
# Roll back service to previous stable task definition revision (e.g. revision 4)
aws ecs update-service \
  --cluster careerai-production-cluster \
  --service careerai-production-service \
  --task-definition careerai-production-api:<PREVIOUS_REVISION>
```

### Database Schema Rollback (if required):
Run an Alembic downgrade task:
```bash
aws ecs run-task \
  --cluster careerai-production-cluster \
  --task-definition careerai-production-api \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[<PRIVATE_SUBNET_1>],securityGroups=[<ECS_SG_ID>]}" \
  --overrides '{
    "containerOverrides": [
      {
        "name": "api",
        "command": ["alembic", "downgrade", "-1"]
      }
    ]
  }'
```

---

## 9. Observability & Alarms

CloudWatch metrics are actively monitored:
- **High 5xx Errors**: Alarms when ALB reports > 10 HTTP 5xx errors in 60s.
- **Latency Spikes**: Alarms when ALB `TargetResponseTime` exceeds 500ms for 3 consecutive minutes.
- **RDS CPU Spike**: Alarms when MySQL CPU utilization exceeds 80% for 10 minutes.
- **Log Stream**: View real-time JSON logs via:
  ```bash
  aws logs tail /ecs/careerai-production --follow
  ```
