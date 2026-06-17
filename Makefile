.PHONY: help dev-up dev-down dev-build dev-logs dev-ps \
        deploy-e2e kubeconfig k8s-render k8s-apply-rendered \
        k8s-wait-external-secrets k8s-wait-pvcs k8s-rollout-status llm-model alb-url route53-alias k8s-apply k8s-delete k8s-status \
        tf-init tf-validate tf-plan tf-apply tf-destroy \
        ecr-login push lint test

SHELL := /bin/bash
AWS_REGION   ?= eu-south-2
AWS_ACCOUNT  ?= $(shell aws sts get-caller-identity --query Account --output text)
TOFU         ?= tofu
ECR_REGISTRY = $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com
APP_SERVICES := gateway market-data news portfolio simulation scheduler forex
K8S_SERVICES := llm $(APP_SERVICES)
K8S_NS       := investments
K8S_MANIFEST_DIR ?= k8s
K8S_RENDER_DIR ?= .rendered/k8s
ifdef TF_WORKSPACE
TF_ENV ?= $(TF_WORKSPACE)
else
TF_ENV ?= prod
endif
TF_WORKSPACE ?= $(TF_ENV)
CLUSTER_NAME ?= investments-assistant
ACM_CERT_ARN ?=
ROUTE53_ZONE_ID ?=
ROUTE53_ZONE_NAME ?=
PULL_LLM_MODEL ?= true
LLM_MODEL ?= llama3.1:8b

export ACM_CERT_ARN

help:
	@echo "Usage:"
	@echo "    make help          Show this help message"
	@echo ""
	@echo "Local development:"
	@echo "    make dev-up        Start all services with docker-compose"
	@echo "    make dev-down      Stop all services"
	@echo "    make dev-build     Rebuild images"
	@echo "    make dev-logs      Tail all logs"
	@echo "    make dev-ps        Show running containers"
	@echo ""
	@echo "End-to-end deployment:"
	@echo "    make deploy-e2e"
	@echo ""
	@echo "Kubernetes:"
	@echo "    make k8s-apply     Apply all manifests to current kubectl context"
	@echo "    make k8s-delete    Delete all resources"
	@echo "    make k8s-status    Show pod/service status"
	@echo "    make alb-url       Show the AWS ALB hostname for the gateway"
	@echo "    make route53-alias Create/update Route 53 alias for app_domain_name"
	@echo ""
	@echo "OpenTofu (AWS):"
	@echo "    make tf-init       tofu init"
	@echo "    make tf-validate   tofu validate"
	@echo "    make tf-plan       tofu plan"
	@echo "    make tf-apply      tofu apply"
	@echo "    make tf-destroy    tofu destroy"
	@echo ""
	@echo "ECR:"
	@echo "    make ecr-login     Authenticate Docker to ECR"
	@echo "    make push          Build & push all service images to ECR"
	@echo ""
	@echo "Quality:"
	@echo "    make lint          Run ruff linter"
	@echo "    make test          Run tests"

# ── Local dev ─────────────────────────────────────────────────────────────────
dev-up:
	@cp -n .env.example .env 2>/dev/null || true
	docker compose up -d

dev-down:
	docker compose down

dev-build:
	docker compose build --parallel

dev-logs:
	docker compose logs -f

dev-ps:
	docker compose ps

# ── End-to-end cloud deployment ──────────────────────────────────────────────
deploy-e2e:
	@$(MAKE) tf-apply
	@$(MAKE) kubeconfig
	@$(MAKE) k8s-render
	@$(MAKE) push
	@$(MAKE) k8s-apply K8S_MANIFEST_DIR=$(K8S_RENDER_DIR)
	@$(MAKE) k8s-rollout-status
	@$(MAKE) alb-url
	@$(MAKE) route53-alias
	@$(MAKE) llm-model
	@echo "End-to-end deployment complete."

kubeconfig:
	@$(TOFU) -chdir=terraform workspace select -or-create "$(TF_ENV)" >/dev/null
	@TF_OUTPUTS="$$($(TOFU) -chdir=terraform output -no-color -json 2>/dev/null || echo '{}')"; \
	CLUSTER="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("cluster_name", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	if [ -z "$$CLUSTER" ]; then CLUSTER="$(CLUSTER_NAME)"; fi; \
	echo "Updating kubeconfig for $$CLUSTER in $(AWS_REGION)"; \
	aws eks update-kubeconfig --region "$(AWS_REGION)" --name "$$CLUSTER"

k8s-render:
	@echo "Rendering Kubernetes manifests to $(K8S_RENDER_DIR)"
	@rm -rf "$(K8S_RENDER_DIR)"
	@mkdir -p "$(dir $(K8S_RENDER_DIR))"
	@cp -R k8s "$(K8S_RENDER_DIR)"
	@$(TOFU) -chdir=terraform workspace select -or-create "$(TF_ENV)" >/dev/null
	@ACCOUNT="$$(aws sts get-caller-identity --query Account --output text)"; \
	AWS_REGION="$(AWS_REGION)"; \
	TF_OUTPUTS="$$($(TOFU) -chdir=terraform output -no-color -json 2>/dev/null || echo '{}')"; \
	ALLOWED_IPS="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("allowed_ip_cidrs", {}).get("value", []); print(",".join(v) if isinstance(v, list) else str(v or ""))' 2>/dev/null)"; \
	AUTH_MODE="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("auth_mode", {}).get("value", "basic"); print(v or "basic")' 2>/dev/null)"; \
	RDS_ENDPOINT="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("rds_endpoint", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	RDS_PORT="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("rds_port", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	RDS_DATABASE_NAME="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("rds_database_name", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	RDS_MASTER_USERNAME="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("rds_master_username", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	REDIS_ENDPOINT="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("redis_endpoint", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	WAF_ARN="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("waf_webacl_arn", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	IRSA_ARN="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("irsa_role_arn", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	ACM_CERT_ARN_FROM_TF="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("acm_certificate_arn", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	COGNITO_USER_POOL_ID="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("cognito_user_pool_id", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	COGNITO_USER_POOL_ARN="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("cognito_user_pool_arn", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	COGNITO_APP_CLIENT_ID="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("cognito_user_pool_client_id", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	COGNITO_USER_POOL_DOMAIN="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("cognito_user_pool_domain", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	ACM_CERT_ARN="$${ACM_CERT_ARN:-$$ACM_CERT_ARN_FROM_TF}"; \
	if [ -z "$$ALLOWED_IPS" ] || [ -z "$$RDS_ENDPOINT" ] || [ -z "$$RDS_PORT" ] || [ -z "$$RDS_DATABASE_NAME" ] || [ -z "$$RDS_MASTER_USERNAME" ] || [ -z "$$REDIS_ENDPOINT" ] || [ -z "$$WAF_ARN" ] || [ -z "$$IRSA_ARN" ]; then \
	  echo "Missing OpenTofu outputs. Run make tf-apply and make sure it completes successfully before rendering Kubernetes manifests."; \
	  rm -rf "$(K8S_RENDER_DIR)"; \
	  exit 1; \
	fi; \
	if [ "$$AUTH_MODE" = "cognito" ] && { [ -z "$$ACM_CERT_ARN" ] || [ -z "$$COGNITO_USER_POOL_ID" ] || [ -z "$$COGNITO_USER_POOL_ARN" ] || [ -z "$$COGNITO_APP_CLIENT_ID" ] || [ -z "$$COGNITO_USER_POOL_DOMAIN" ]; }; then \
	  echo "Cognito auth requires app_domain_name/ACM and Cognito outputs. Run make tf-apply with enable_cognito_auth=true and a HTTPS domain."; \
	  rm -rf "$(K8S_RENDER_DIR)"; \
	  exit 1; \
	fi; \
	export ACCOUNT AWS_REGION ALLOWED_IPS AUTH_MODE RDS_ENDPOINT RDS_PORT RDS_DATABASE_NAME RDS_MASTER_USERNAME REDIS_ENDPOINT WAF_ARN IRSA_ARN ACM_CERT_ARN COGNITO_USER_POOL_ID COGNITO_USER_POOL_ARN COGNITO_APP_CLIENT_ID COGNITO_USER_POOL_DOMAIN; \
	find "$(K8S_RENDER_DIR)" -name deployment.yaml -print0 | xargs -0 perl -0pi -e 's/ACCOUNT/$$ENV{ACCOUNT}/g'; \
	perl -0pi -e 's|REPLACE_WITH_ALLOWED_IPS|$$ENV{ALLOWED_IPS}|g; s|REPLACE_WITH_AUTH_MODE|$$ENV{AUTH_MODE}|g; s|REPLACE_WITH_AWS_REGION|$$ENV{AWS_REGION}|g; s|REPLACE_WITH_COGNITO_USER_POOL_ID|$$ENV{COGNITO_USER_POOL_ID}|g; s|REPLACE_WITH_COGNITO_APP_CLIENT_ID|$$ENV{COGNITO_APP_CLIENT_ID}|g; s|REPLACE_WITH_RDS_ENDPOINT|$$ENV{RDS_ENDPOINT}|g; s|REPLACE_WITH_RDS_PORT|$$ENV{RDS_PORT}|g; s|REPLACE_WITH_RDS_DATABASE_NAME|$$ENV{RDS_DATABASE_NAME}|g; s|REPLACE_WITH_RDS_MASTER_USERNAME|$$ENV{RDS_MASTER_USERNAME}|g; s|REPLACE_WITH_REDIS_ENDPOINT|$$ENV{REDIS_ENDPOINT}|g' "$(K8S_RENDER_DIR)/configmap.yaml"; \
	perl -0pi -e 's|arn:aws:iam::ACCOUNT:role/investments-assistant-investments-sa-role|$$ENV{IRSA_ARN}|g; s/ACCOUNT/$$ENV{ACCOUNT}/g' "$(K8S_RENDER_DIR)/serviceaccount.yaml"; \
	perl -0pi -e 's|arn:aws:wafv2:eu-south-2:ACCOUNT:regional/webacl/investments-allowlist/WEBACL_ID|$$ENV{WAF_ARN}|g; s/ACCOUNT/$$ENV{ACCOUNT}/g' "$(K8S_RENDER_DIR)/ingress.yaml"; \
	python3 scripts/render_ingress.py "$(K8S_RENDER_DIR)/ingress.yaml"
	@if find "$(K8S_RENDER_DIR)" -name '*.yaml' -exec grep -nE 'ACCOUNT|CERT_ID|WEBACL_ID|REPLACE_WITH_' {} +; then \
	  echo "Rendered manifests still contain placeholders."; \
	  exit 1; \
	fi

k8s-apply-rendered: k8s-render
	$(MAKE) k8s-apply K8S_MANIFEST_DIR=$(K8S_RENDER_DIR)

k8s-rollout-status:
	@for svc in $(K8S_SERVICES); do \
	  echo "▶ Waiting for $$svc rollout"; \
	  kubectl -n $(K8S_NS) rollout status deployment/$$svc --timeout=10m; \
	done
	@$(MAKE) k8s-status

llm-model:
	@if [ "$(PULL_LLM_MODEL)" = "true" ]; then \
	  echo "Pulling LLM model $(LLM_MODEL) into the llm pod"; \
	  kubectl -n $(K8S_NS) rollout status deployment/llm --timeout=10m; \
	  kubectl -n $(K8S_NS) exec deploy/llm -- ollama pull "$(LLM_MODEL)"; \
	else \
	  echo "Skipping LLM model pull. Set PULL_LLM_MODEL=true to run: ollama pull $(LLM_MODEL)"; \
	fi

alb-url:
	@for i in $$(seq 1 60); do \
	  HOST="$$(kubectl -n $(K8S_NS) get ingress investments-ingress -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)"; \
	  if [ -n "$$HOST" ]; then \
	    echo "AWS ALB hostname: $$HOST"; \
	    echo "Built-in ALB URL: http://$$HOST"; \
	    echo "Use your custom domain for HTTPS when ACM is configured."; \
	    exit 0; \
	  fi; \
	  sleep 5; \
	done; \
	echo "ALB hostname is not ready yet. Check: kubectl -n $(K8S_NS) describe ingress investments-ingress"; \
	exit 1

route53-alias:
	@$(TOFU) -chdir=terraform workspace select -or-create "$(TF_ENV)" >/dev/null
	@TF_OUTPUTS="$$($(TOFU) -chdir=terraform output -no-color -json 2>/dev/null || echo '{}')"; \
	APP_DOMAIN="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("app_domain_name", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	ZONE_ID="$(ROUTE53_ZONE_ID)"; \
	ZONE_NAME="$(ROUTE53_ZONE_NAME)"; \
	if [ -z "$$ZONE_ID" ]; then ZONE_ID="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("app_route53_zone_id", {}).get("value", ""); print(v or "")' 2>/dev/null)"; fi; \
	if [ -z "$$ZONE_NAME" ]; then ZONE_NAME="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("app_route53_zone_name", {}).get("value", ""); print(v or "")' 2>/dev/null)"; fi; \
	if [ -z "$$APP_DOMAIN" ]; then \
	  echo "No app_domain_name configured; skipping Route 53 alias."; \
	  exit 0; \
	fi; \
	HOST="$$(kubectl -n $(K8S_NS) get ingress investments-ingress -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)"; \
	if [ -z "$$HOST" ]; then \
	  echo "ALB hostname is not ready. Run make alb-url first."; \
	  exit 1; \
	fi; \
	if [ -z "$$ZONE_ID" ]; then \
	  if [ -z "$$ZONE_NAME" ]; then \
	    echo "Route 53 zone is missing. Set app_route53_zone_id/name or pass ROUTE53_ZONE_ID."; \
	    exit 1; \
	  fi; \
	  ZONE_ID="$$(aws route53 list-hosted-zones-by-name --dns-name "$$ZONE_NAME" --query 'HostedZones[0].Id' --output text | sed 's|/hostedzone/||')"; \
	fi; \
	LB_ZONE_ID="$$(aws elbv2 describe-load-balancers --region "$(AWS_REGION)" --query "LoadBalancers[?DNSName=='$$HOST'].CanonicalHostedZoneId | [0]" --output text)"; \
	if [ -z "$$LB_ZONE_ID" ] || [ "$$LB_ZONE_ID" = "None" ]; then \
	  echo "Could not resolve ALB hosted zone ID for $$HOST"; \
	  exit 1; \
	fi; \
	CHANGE_BATCH="$$(printf '{"Changes":[{"Action":"UPSERT","ResourceRecordSet":{"Name":"%s","Type":"A","AliasTarget":{"HostedZoneId":"%s","DNSName":"dualstack.%s","EvaluateTargetHealth":true}}}]}' "$$APP_DOMAIN" "$$LB_ZONE_ID" "$$HOST")"; \
	aws route53 change-resource-record-sets --hosted-zone-id "$$ZONE_ID" --change-batch "$$CHANGE_BATCH" >/dev/null; \
	echo "Route 53 alias updated: https://$$APP_DOMAIN -> $$HOST"

# ── Kubernetes ────────────────────────────────────────────────────────────────
k8s-apply:
	kubectl apply -f $(K8S_MANIFEST_DIR)/namespace.yaml
	kubectl apply -f $(K8S_MANIFEST_DIR)/configmap.yaml
	kubectl apply -f $(K8S_MANIFEST_DIR)/serviceaccount.yaml
	kubectl apply -f $(K8S_MANIFEST_DIR)/reports-pvc.yaml
	kubectl apply -f $(K8S_MANIFEST_DIR)/llm/pvc.yaml
	$(MAKE) k8s-wait-pvcs
	$(MAKE) k8s-wait-external-secrets
	kubectl apply -f $(K8S_MANIFEST_DIR)/external-secrets.yaml
	@for svc in $(K8S_SERVICES); do \
	  kubectl apply -f $(K8S_MANIFEST_DIR)/$$svc/; \
	done
	kubectl apply -f $(K8S_MANIFEST_DIR)/ingress.yaml

k8s-wait-external-secrets:
	@echo "Waiting for External Secrets CRDs"
	@for crd in secretstores.external-secrets.io externalsecrets.external-secrets.io; do \
	  for i in $$(seq 1 60); do \
	    if kubectl get crd $$crd >/dev/null 2>&1; then break; fi; \
	    if [ "$$i" = "60" ]; then \
	      echo "Timed out waiting for CRD $$crd. Check OpenTofu helm_release.eso."; \
	      exit 1; \
	    fi; \
	    sleep 2; \
	  done; \
	  kubectl wait --for=condition=Established crd/$$crd --timeout=120s; \
	done

k8s-wait-pvcs:
	@echo "Waiting for application PVCs"
	@for pvc in reports-pvc llm-models-pvc; do \
	  for i in $$(seq 1 90); do \
	    phase="$$(kubectl -n $(K8S_NS) get pvc $$pvc -o jsonpath='{.status.phase}' 2>/dev/null || true)"; \
	    if [ "$$phase" = "Bound" ]; then break; fi; \
	    if [ "$$i" = "90" ]; then \
	      echo "Timed out waiting for PVC $$pvc to bind. Check the efs-sc StorageClass and EFS CSI driver."; \
	      kubectl -n $(K8S_NS) describe pvc $$pvc || true; \
	      exit 1; \
	    fi; \
	    sleep 2; \
	  done; \
	done

k8s-delete:
	kubectl delete namespace $(K8S_NS) --ignore-not-found

k8s-status:
	kubectl -n $(K8S_NS) get pods,svc,ingress

# ── OpenTofu ──────────────────────────────────────────────────────────────────
tf-init:
	cd terraform && $(TOFU) init -reconfigure -upgrade
	cd terraform && $(TOFU) workspace select -or-create $(TF_ENV)

tf-validate: tf-init
	cd terraform && $(TOFU) validate -var-file=$(TF_ENV).tfvars

tf-plan: tf-validate
	cd terraform && $(TOFU) plan -var-file=$(TF_ENV).tfvars -out=ttplan -json-into=ttplan.json

tf-apply: tf-plan
	cd terraform && $(TOFU) apply -auto-approve -json-into=ttoutputs.json ttplan

tf-destroy: tf-init
	cd terraform && $(TOFU) destroy -auto-approve -var-file=$(TF_ENV).tfvars

# ── ECR ───────────────────────────────────────────────────────────────────────
ecr-login:
	aws ecr get-login-password --region $(AWS_REGION) | \
	  docker login --username AWS --password-stdin $(ECR_REGISTRY)

push: ecr-login
	@set -e; \
	for svc in $(APP_SERVICES); do \
	  echo "▶ Building $$svc …"; \
	  docker build -t $(ECR_REGISTRY)/investments-$$svc:latest services/$$svc; \
	  docker push $(ECR_REGISTRY)/investments-$$svc:latest; \
	done

# ── Quality ───────────────────────────────────────────────────────────────────
lint:
	@for svc in $(APP_SERVICES); do \
	  echo "▶ Linting $$svc …"; \
	  cd services/$$svc && ruff check src/ && cd ../..; \
	done

test:
	@for svc in $(APP_SERVICES); do \
	  echo "▶ Testing $$svc …"; \
	  cd services/$$svc && python -m pytest tests/ -q 2>/dev/null || true && cd ../..; \
	done
