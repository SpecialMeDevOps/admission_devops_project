These manifests are intentionally beginner-friendly practice defaults.

Before applying them, create `admission-secrets` from a secret manager or replace the example values locally. Never commit real credentials. The application Deployment starts with `admission-api:latest`; Jenkins updates it with `kubectl set image` after pushing to ECR or Docker Hub.

The LoadBalancer Service makes the site reachable on AWS. `ingress.yaml` is optional and requires an ingress controller and a real DNS host. The in-cluster PostgreSQL deployment is suitable for practice; use Amazon RDS or another managed database for production.
