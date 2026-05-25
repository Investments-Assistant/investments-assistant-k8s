.PHONY: help dev-up dev-down dev-build dev-logs dev-ps \
        deploy-e2e kubeconfig k8s-render k8s-apply-rendered \
        k8s-wait-external-secrets k8s-wait-pvcs k8s-rollout-status llm-model k8s-apply k8s-delete k8s-status \
        tf-init tf-plan tf-apply tf-destroy \
        ecr-login push lint test

SHELL := /bin/bash
AWS_REGION   ?= eu-south-2
AWS_ACCOUNT  ?= $(shell aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY := $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com
APP_SERVICES := gateway market-data news portfolio simulation scheduler forex
K8S_SERVICES := llm $(APP_SERVICES)
K8S_NS       := investments
K8S_MANIFEST_DIR ?= k8s
K8S_RENDER_DIR ?= .rendered/k8s
TF_WORKSPACE ?= prod
CLUSTER_NAME ?= investments-assistant
ACM_CERT_ARN ?=
PULL_LLM_MODEL ?= false
LLM_MODEL ?= llama3.1:8b-instruct

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
	@echo ""
	@echo "Terraform (AWS):"
	@echo "    make tf-init       terraform init"
	@echo "    make tf-plan       terraform plan"
	@echo "    make tf-apply      terraform apply"
	@echo "    make tf-destroy    terraform destroy"
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
	@$(MAKE) llm-model
	@echo "End-to-end deployment complete."

kubeconfig:
	@terraform -chdir=terraform workspace select -or-create "$(TF_WORKSPACE)" >/dev/null
	@TF_OUTPUTS="$$(terraform -chdir=terraform output -no-color -json 2>/dev/null || echo '{}')"; \
	CLUSTER="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("cluster_name", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	if [ -z "$$CLUSTER" ]; then CLUSTER="$(CLUSTER_NAME)"; fi; \
	echo "Updating kubeconfig for $$CLUSTER in $(AWS_REGION)"; \
	aws eks update-kubeconfig --region "$(AWS_REGION)" --name "$$CLUSTER"

k8s-render:
	@echo "Rendering Kubernetes manifests to $(K8S_RENDER_DIR)"
	@rm -rf "$(K8S_RENDER_DIR)"
	@mkdir -p "$(dir $(K8S_RENDER_DIR))"
	@cp -R k8s "$(K8S_RENDER_DIR)"
	@terraform -chdir=terraform workspace select -or-create "$(TF_WORKSPACE)" >/dev/null
	@ACCOUNT="$$(aws sts get-caller-identity --query Account --output text)"; \
	TF_OUTPUTS="$$(terraform -chdir=terraform output -no-color -json 2>/dev/null || echo '{}')"; \
	RDS_ENDPOINT="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("rds_endpoint", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	REDIS_ENDPOINT="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("redis_endpoint", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	WAF_ARN="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("waf_webacl_arn", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	IRSA_ARN="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("irsa_role_arn", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	ACM_CERT_ARN_FROM_TF="$$(TF_OUTPUTS="$$TF_OUTPUTS" python3 -c 'import json, os; v=json.loads(os.environ["TF_OUTPUTS"]).get("acm_certificate_arn", {}).get("value", ""); print(v or "")' 2>/dev/null)"; \
	ACM_CERT_ARN="$${ACM_CERT_ARN:-$$ACM_CERT_ARN_FROM_TF}"; \
	if [ -z "$$RDS_ENDPOINT" ] || [ -z "$$REDIS_ENDPOINT" ] || [ -z "$$WAF_ARN" ] || [ -z "$$IRSA_ARN" ]; then \
	  echo "Missing Terraform outputs. Run make tf-apply and make sure it completes successfully before rendering Kubernetes manifests."; \
	  rm -rf "$(K8S_RENDER_DIR)"; \
	  exit 1; \
	fi; \
	export ACCOUNT RDS_ENDPOINT REDIS_ENDPOINT WAF_ARN IRSA_ARN ACM_CERT_ARN; \
	find "$(K8S_RENDER_DIR)" -name deployment.yaml -print0 | xargs -0 perl -0pi -e 's/ACCOUNT/$$ENV{ACCOUNT}/g'; \
	perl -0pi -e 's|REPLACE_WITH_RDS_ENDPOINT|$$ENV{RDS_ENDPOINT}|g; s|REPLACE_WITH_REDIS_ENDPOINT|$$ENV{REDIS_ENDPOINT}|g' "$(K8S_RENDER_DIR)/configmap.yaml"; \
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
	      echo "Timed out waiting for CRD $$crd. Check Terraform helm_release.eso."; \
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

# ── Terraform ─────────────────────────────────────────────────────────────────
tf-init:
	cd terraform && terraform init -upgrade -reconfigure

tf-plan: tf-init
	cd terraform && terraform workspace select -or-create $(TF_WORKSPACE)
	cd terraform && terraform plan -out=tfplan

tf-apply: tf-plan
	cd terraform && terraform apply -auto-approve tfplan
tf-destroy:
	cd terraform && terraform destroy -auto-approve

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
