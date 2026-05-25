output "irsa_role_arn" { value = aws_iam_role.investments_sa.arn }
output "eso_role_arn" { value = aws_iam_role.eso.arn }
output "alb_logs_bucket" { value = aws_s3_bucket.alb_logs.bucket }
