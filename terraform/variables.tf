variable "aws_region" {
  description = "AWS region for the platform."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short name used in AWS resource names."
  type        = string
  default     = "admission-platform"
}

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
  default     = "admission-eks"
}

variable "ecr_repository_name" {
  description = "ECR repository name used by the ECR registry option."
  type        = string
  default     = "admission-api"
}

variable "vpc_cidr" {
  description = "CIDR range for the VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "availability_zones" {
  description = "At least two AZs are recommended for EKS."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "node_instance_types" {
  description = "EC2 instance types for the managed node group."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "node_min_size" {
  type    = number
  default = 1
}

variable "node_max_size" {
  type    = number
  default = 3
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default = {
    ManagedBy = "terraform"
    Project   = "admission-platform"
  }
}
