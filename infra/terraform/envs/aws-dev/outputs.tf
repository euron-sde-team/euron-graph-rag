output "urls" {
  description = "Public URLs of the web app and the API."
  value       = module.graphrag.urls
}

output "ecr_repository_urls" {
  description = "Image repositories."
  value       = module.graphrag.ecr_repository_urls
}

output "cluster_name" {
  description = "ECS cluster."
  value       = module.graphrag.cluster_name
}

output "service_names" {
  description = "ECS services."
  value       = module.graphrag.service_names
}

output "cli_task_definition" {
  description = "Task definition for one-off CLI tasks."
  value       = module.graphrag.cli_task_definition
}

output "cli_security_group_id" {
  description = "Security group for one-off CLI tasks."
  value       = module.graphrag.cli_security_group_id
}

output "private_subnet_ids" {
  description = "Private subnets for one-off tasks."
  value       = module.graphrag.private_subnet_ids
}

output "load_balancer_dns_name" {
  description = "Point app.<domain> and api.<domain> here when the zone is not in Route53."
  value       = module.graphrag.load_balancer_dns_name
}

output "certificate_validation_records" {
  description = "DNS records to publish when the zone is not in Route53."
  value       = module.graphrag.certificate_validation_records
}

output "jobs_dlq_url" {
  description = "Dead-letter queue to inspect when job alarms fire."
  value       = module.graphrag.jobs_dlq_url
}
