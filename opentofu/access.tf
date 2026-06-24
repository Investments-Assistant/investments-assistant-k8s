locals {
  github_actions_deploy_role_arn = coalesce(
    var.github_actions_deploy_role_arn,
    "arn:aws:iam::${local.account_id}:role/${var.github_actions_deploy_role_name}"
  )
}

resource "aws_eks_access_entry" "github_actions_deploy" {
  count = var.enable_github_actions_deploy_access ? 1 : 0

  cluster_name  = module.eks.cluster_name
  principal_arn = local.github_actions_deploy_role_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "github_actions_deploy_admin" {
  count = var.enable_github_actions_deploy_access ? 1 : 0

  cluster_name  = module.eks.cluster_name
  principal_arn = local.github_actions_deploy_role_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.github_actions_deploy]
}
