output "cluster_name" {
  value       = module.eks.cluster_name
  description = "EKS cluster name for kubectl configuration."
}

output "cluster_endpoint" {
  value       = module.eks.cluster_endpoint
  description = "EKS API endpoint."
}

output "ecr_repository_url" {
  value       = module.ecr.repository_url
  description = "ECR URL for the image tag."
}

output "kubectl_config_command" {
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
  description = "Command to configure kubectl."
}
