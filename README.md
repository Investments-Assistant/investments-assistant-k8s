# Investments Assistant K8s

This repository contains the Kubernetes-first version of the Investments
Assistant. It packages the assistant as multiple FastAPI services, deploys them
to EKS, and provisions the AWS infrastructure needed to run them.

The key idea is simple: the gateway owns the user experience and agent loop, and
specialist services own tools. The gateway talks to those services over internal
HTTP tool calls. OpenTofu provides the AWS pieces; Kubernetes runs the service
pods.

## System Diagram

```mermaid
flowchart TB
    User[User] --> ALB[ALB Ingress]
    ACM[ACM OpenTofu module] --> ALB
    ALB --> WAF[WAF OpenTofu module]
    WAF --> Gateway[gateway service]

    Gateway --> LLM[self-hosted llm service]
    Gateway --> MarketData[market-data service]
    Gateway --> Forex[forex service]
    Gateway --> News[news service]
    Gateway --> Portfolio[portfolio service]
    Gateway --> Simulation[simulation service]
    Gateway --> Scheduler[scheduler service]

    Scheduler --> Gateway
    Scheduler --> News
    Scheduler --> MarketData

    Gateway --> Redis[ElastiCache OpenTofu module]
    Portfolio --> Redis

    Gateway --> DB[Aurora PostgreSQL OpenTofu module]
    News --> DB
    Portfolio --> DB
    Simulation --> DB
    Scheduler --> DB

    Gateway --> EFS[EFS from EKS OpenTofu module]
    Scheduler --> EFS
    LLM --> ModelPVC[llm-models-pvc on EFS]

    ECR[ECR OpenTofu module] --> K8s[Kubernetes Deployments]
    Secrets[Secrets/IAM OpenTofu module] --> K8s
    VPC[VPC OpenTofu module] --> EKS[EKS OpenTofu module]
    EKS --> K8s
```

## Repository Layout

| Path | Purpose |
| --- | --- |
| `terraform/` | AWS infrastructure stack that consumes shared modules from `Investments-Assistant/terraform-modules`. Start with `terraform/README.md`. |
| `k8s/` | Kubernetes namespace, config, secrets wiring, service deployments, services, PVC, and ingress. See `k8s/README.md`. |
| `services/` | FastAPI microservices. See `services/README.md` and each service README. |
| `.github/workflows/` | CI workflows for image build/push and EKS deployment. |
| `docker-compose.yml` | Local development topology with app services, PostgreSQL, Redis, and Ollama. |
| `Makefile` | Common local, Kubernetes, OpenTofu, and ECR commands. |

## How The Pieces Fit

OpenTofu builds the AWS infrastructure:

- The VPC module creates networking.
- The EKS module creates the cluster, general worker node group, dedicated LLM
  node group, EFS storage, and IAM roles for cluster add-ons.
- The ECR module creates one image repository per service.
- The ACM module creates and validates the ALB HTTPS certificate when
  `app_domain_name` and either `app_route53_zone_id` or
  `app_route53_zone_name` are set.
- The Cognito module creates the application user pool and role groups when
  `enable_cognito_auth=true`.
- The RDS and ElastiCache modules provide PostgreSQL and Redis.
- The WAF module protects the public ALB.
- The secrets module creates IAM roles and permissions for Kubernetes service
  accounts and External Secrets.

Helm installs the in-cluster add-ons from the separate
`Investments-Assistant/helm-charts` repository:

- AWS EFS CSI driver plus the `efs-sc` StorageClass.
- AWS Load Balancer Controller.
- External Secrets Operator and CRDs.

Kubernetes manifests then deploy the application:

- `gateway` is the only external service, reached through ALB Ingress.
- `market-data`, `forex`, `news`, `portfolio`, `simulation`, and `scheduler`
  are cluster-internal services.
- `investments-config` provides non-secret settings.
- `investments-secrets` is populated from AWS Secrets Manager by External
  Secrets Operator.
- `reports-pvc` is mounted by gateway and scheduler for generated reports.
- `llm-models-pvc` is mounted by the Ollama deployment for local model storage.

The service layer provides agent capabilities:

- `gateway` handles UI/API/WebSocket traffic, self-hosted LLM calls, and tool routing.
- `market-data` provides stocks, crypto, indicators, options, ticker search, and
  earnings tools.
- `forex` provides FX candles, spot rates, and central bank rates.
- `news` provides fresh and stored news search plus ingestion.
- `portfolio` provides broker integrations and trade safety controls.
- `simulation` provides backtesting.
- `scheduler` coordinates recurring ingestion, autonomous scans, and reports.

For implementation details, use the READMEs in `terraform/`, `k8s/`, and
`services/`.

## Local Development

```bash
cp .env.example .env
make dev-up
```

Gateway runs on `http://localhost:8000`. Docker Compose starts PostgreSQL,
Redis, the local Ollama-compatible LLM service, and all seven application services.

Before using chat locally, load a model into Ollama:

```bash
docker compose exec llm ollama pull llama3.1:8b-instruct
```

Useful commands:

```bash
make dev-logs
make dev-down
make lint
```

## Cloud Deployment Flow

1. Fill `terraform/prod.tfvars` from `terraform/env.tfvars.example`.
2. Set `allowed_ip_cidrs` to the public IPv4 AWS sees from your home VPN egress,
   for example `203.0.113.10/32`.
3. Set `UI_AUTH_USERNAME` and `UI_AUTH_PASSWORD` in `app_secret_values` for the
   Basic Auth fallback path.
4. Set `app_domain_name` and either `app_route53_zone_id` or
   `app_route53_zone_name` if you want OpenTofu to create the ALB HTTPS
   certificate.
5. Set `enable_cognito_auth=true` if you want Cognito user login and
   `viewer`/`investor`/`admin` role groups. This requires step 4.
6. Clone `Investments-Assistant/helm-charts` next to this repository, or set
   `HELM_CHARTS_DIR` to its path.
7. Run the end-to-end deployment:

```bash
make deploy-e2e
```

`deploy-e2e` runs OpenTofu, updates kubeconfig, builds and pushes service
images to ECR, renders Kubernetes manifests with OpenTofu outputs, installs or
updates the Helm add-ons, applies the manifests, updates the Route 53 ALIAS for
`app_domain_name` when configured, and waits for rollouts. OpenTofu writes
`db_password` from
`$(TF_ENV).tfvars` into the `investments/prod` Secrets Manager secret as
`POSTGRES_PASSWORD`; the rendered ConfigMap uses OpenTofu outputs for the RDS
host, port, database name, username, and application IP allowlist. Rendered
manifests are written to `.rendered/k8s` and are not committed.

If you already have a certificate outside OpenTofu, you can override the
OpenTofu output with `ACM_CERT_ARN=arn:aws:acm:...`.

If no certificate is available, the generated ingress is HTTP-only. Set
`app_domain_name` and a Route 53 zone in OpenTofu to enable HTTPS.

For the no-Route-53 path, use the AWS-managed ALB hostname:

```bash
make alb-url
```

That URL is not localhost; it is the public ALB entry point protected by WAF and
gateway Basic Auth. Without your own domain and ACM certificate, the ALB
hostname is HTTP-only, so credentials are not encrypted in transit even though
the WAF allowlist limits who can reach it.

For HTTPS, browse to your configured domain, not the raw ALB hostname. The raw
`*.elb.amazonaws.com` name cannot use your ACM certificate. The deployment flow
creates the ACM certificate, attaches it to the ALB HTTPS listener, and upserts
a Route 53 ALIAS from `app_domain_name` to the ALB:

```bash
make route53-alias
```

When Cognito auth is enabled, users sign in through the ALB/Cognito hosted UI.
The gateway validates Cognito tokens and applies group-based permissions:
`viewer` can chat about news, `investor` can use non-portfolio analysis tools,
and `admin` can use everything.

By default the command does not pull an Ollama model from an external registry.
For non-air-gapped deployments, add `PULL_LLM_MODEL=true` to pull the configured
model into the `llm` pod.

The Makefile assumes AWS region `eu-south-2` by default. Keep OpenTofu, ECR,
ACM, WAF, Kubernetes manifests, and GitHub Actions aligned to the same region.
OpenTofu targets EKS Kubernetes `1.33` by default.

GitHub Actions uses AWS OIDC with separate roles created by `core-infra`:

- `AWS_BUILD_ROLE_ARN` for `build-push.yml`.
- `AWS_DEPLOY_ROLE_ARN` for `deploy.yml`.

Configure them as repository variables before running the workflows. The
values come from the `core-infra` AWS stack outputs
`github_actions_build_role_arn` and `github_actions_deploy_role_arn`. If either
role ARN is missing, the relevant workflow fails before
`aws-actions/configure-aws-credentials` with a direct configuration error. The
k8s OpenTofu stack creates an EKS access entry for
`investments-assistant-github-actions-deploy-role` so `kubectl apply` can use
the deploy role.

The self-hosted LLM deployment is scheduled onto a dedicated EKS node group by
default. Keep `enable_llm_node_group=true` in OpenTofu unless you resize the
general worker nodes enough to run the Ollama pod.

## Important Notes

- Do not commit `*.tfvars`, OpenTofu state, `.terraform/`, or plan
  files.
- The gateway no longer uses a hosted LLM API. It calls the self-hosted
  OpenAI-compatible endpoint configured by `LLM_BASE_URL`.
- `EXTERNAL_API_ACCESS=false` is the default. With that setting, market data,
  news ingestion, and broker tools return a disabled message instead of calling
  third-party services.
- The application can place trades when configured in `auto` mode. Keep broker
  credentials, symbol allowlists, and trade limits conservative.
- Generated reports are not financial advice.
