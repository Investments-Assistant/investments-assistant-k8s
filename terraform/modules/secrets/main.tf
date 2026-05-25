terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

# ── IRSA role for the investments K8s ServiceAccount ─────────────────────────
data "aws_iam_policy_document" "irsa_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(var.oidc_provider_url, "https://", "")}:sub"
      values   = ["system:serviceaccount:investments:investments-sa"]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(var.oidc_provider_url, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "investments_sa" {
  name               = "${var.cluster_name}-investments-sa-role"
  assume_role_policy = data.aws_iam_policy_document.irsa_assume.json
}

resource "aws_iam_policy" "investments_sa" {
  name = "${var.cluster_name}-investments-sa-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Read the investments/prod secret
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
        Resource = [var.secrets_manager_secret_arn]
      },
      {
        # Pull/push images in ECR
        Effect = "Allow"
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetAuthorizationToken",
        ]
        Resource = concat(var.ecr_repository_arns, ["*"])
      },
      {
        # Allow associating WAF to ALB (used by Load Balancer Controller)
        Effect   = "Allow"
        Action   = ["wafv2:AssociateWebACL", "wafv2:DisassociateWebACL", "wafv2:GetWebACL"]
        Resource = [var.waf_webacl_arn, "*"]
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "investments_sa" {
  role       = aws_iam_role.investments_sa.name
  policy_arn = aws_iam_policy.investments_sa.arn
}

# ── ESO ClusterSecretStore IAM role ──────────────────────────────────────────
# ESO needs its own SA in the external-secrets namespace
data "aws_iam_policy_document" "eso_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(var.oidc_provider_url, "https://", "")}:sub"
      values   = ["system:serviceaccount:external-secrets:external-secrets"]
    }
  }
}

resource "aws_iam_role" "eso" {
  name               = "${var.cluster_name}-eso-role"
  assume_role_policy = data.aws_iam_policy_document.eso_assume.json
}

resource "aws_iam_policy" "eso" {
  name = "${var.cluster_name}-eso-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
      Resource = [var.secrets_manager_secret_arn]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eso" {
  role       = aws_iam_role.eso.name
  policy_arn = aws_iam_policy.eso.arn
}

resource "aws_s3_bucket" "alb_logs" {
  bucket        = "investments-alb-logs"
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_policy" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AWSLogDeliveryWrite"
        Effect    = "Allow"
        Principal = { Service = "logdelivery.elasticloadbalancing.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.alb_logs.arn}/investments/AWSLogs/${var.account_id}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      },
    ]
  })
}
