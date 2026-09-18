# Admission Platform DevOps Project

A beginner-friendly admission website built with Flask, PostgreSQL, Docker, Kubernetes, Terraform, AWS EKS, Jenkins, and GitHub webhooks.

The student enters a name, email address, and one supporting document. Flask validates the request, stores admission metadata in PostgreSQL, and stores the uploaded file in a mounted uploads directory. Docker packages the web service. Jenkins builds and pushes the image, provisions AWS infrastructure with Terraform, and deploys the image to EKS.

## 1. Architecture

```text
Developer push
    -> GitHub repository
    -> GitHub webhook
    -> Jenkins declarative pipeline
    -> pytest -> Docker build -> ECR or Docker Hub
    -> Terraform state -> VPC/IAM/EKS/ECR
    -> kubectl -> production namespace on EKS
    -> Flask service + PostgreSQL service
```

This repository contains a practice-grade in-cluster PostgreSQL deployment. For a real production system, replace it with Amazon RDS and use object storage such as S3 for documents.

## 2. Folder structure

```text
app/backend/app.py                 Flask API, form handler, health endpoint
app/backend/requirements.txt       Python dependencies
app/frontend/templates/index.html  Admission form
app/frontend/static/                Browser JavaScript and CSS
tests/test_app.py                   Fast tests using SQLite
Dockerfile                          Production-style Flask image
docker-compose.yml                  Local Flask + PostgreSQL stack
k8s/                                Namespace, app, PostgreSQL, service, secrets
terraform/                          Root Terraform configuration
terraform/modules/{vpc,iam,eks,ecr} Reusable AWS modules
Jenkinsfile                         Jenkins CI/CD pipeline
.github/workflows/README.md         Why Jenkins owns deployment CI/CD
```

## 3. Run locally

1. Install Docker Desktop.
2. Copy `.env.example` to `.env` and set a local password. Do not commit `.env`.
3. Start the stack:

```bash
copy .env.example .env
# Edit .env and replace the example password
docker compose up --build
```

Open `http://localhost:5000`. The web container connects to the `db` service using the compose network. PostgreSQL data and uploaded files use named Docker volumes.

To stop it, run `docker compose down`. Add `-v` only when you intentionally want to delete local database and upload data.

## 4. Application and database

`POST /api/admissions` accepts `multipart/form-data` with `student_name`, `email`, and `document`. Files are limited to 10 MB and the allowed extensions are PDF, Word, PNG, and JPG. The database stores the student name, email, generated stored filename, and timestamp. The original filename is not used as a filesystem path.

The app reads `DATABASE_URL` and `UPLOAD_FOLDER` from environment variables. No database password is in Python source. Tests use a temporary SQLite file; the deployed app uses PostgreSQL.

## 5. Docker

Build and run without Compose:

```bash
docker build -t admission-api:local .
docker run --rm -p 5000:5000 \
  -e DATABASE_URL="postgresql://..." \
  -e UPLOAD_FOLDER=/app/uploads admission-api:local
```

The image uses Python 3.12 slim, a non-root `appuser`, Gunicorn, a health check, and two workers. The `.dockerignore` excludes credentials, Terraform state, caches, and local uploads.

## 6. AWS and Terraform setup

Install AWS CLI, Terraform, kubectl, and Docker. Configure AWS locally with an IAM role or a profile. Jenkins uses its own AWS credential binding; never put keys in this repository.

Copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars` only if you need custom values. That file is ignored by Git. From the repository root:

```bash
cd terraform
terraform init
terraform fmt -recursive
terraform validate
terraform plan
terraform apply
```

The modules create:

- A VPC, internet gateway, two public subnets, route table, and EKS-compatible subnet tags.
- IAM roles for the EKS control plane and managed nodes.
- An EKS cluster and managed node group.
- An ECR repository with scan-on-push enabled.

Public subnets and a managed node group keep this lab understandable. Public subnets and NAT choices should be redesigned before production. Terraform state is the record of resources Terraform manages. Use a remote, locked backend such as S3 plus DynamoDB for a team; this starter keeps backend configuration out so learners can choose the account-specific backend.

### Existing resources and recreate behavior

`RESOURCE_MODE=USE_EXISTING` in Jenkins means Terraform uses the existing state and reconciles changes. A second apply does not recreate unchanged resources. Keep the same backend and workspace. If resources already exist but are not in state, import them with `terraform import` rather than creating a second copy.

`RESOURCE_MODE=RECREATE` is an explicit warning to review the plan. Jenkins requires `CONFIRM_DESTRUCTIVE=true`; Terraform still decides what actually changes from the plan. `ACTION=DESTROY` also requires that confirmation and runs `terraform destroy`. Review the workspace, account, and state before confirming.

## 7. Registry choices

### AWS ECR

Terraform creates `admission-api`. The Jenkins `ECR` option obtains the AWS account ID, tags the image as `<account>.dkr.ecr.<region>.amazonaws.com/admission-api:<build>`, logs in with `aws ecr get-login-password`, and pushes it. EKS node IAM includes read-only ECR access.

### Docker Hub

Create a Docker Hub repository and set the Jenkins `DOCKERHUB_REPOSITORY` parameter to `username/admission-api`. Store a Docker Hub access token in Jenkins username/password credentials named `dockerhub-credentials`. Jenkins logs in without exposing the token and pushes `<repository>:<build>`.

For a private Docker Hub repository, create an `imagePullSecret` in the `production` namespace and reference it from `k8s/deployment.yaml`. A public repository avoids that extra practice step.

## 8. Kubernetes

The deployment uses the configurable namespace name `production`, two Flask replicas, readiness/liveness probes, resource requests, a LoadBalancer Service, and a persistent volume for the practice PostgreSQL database. `k8s/secret.yaml` is an example only and is not applied by Jenkins. Jenkins creates the secret from a Jenkins string credential named `postgres-password`.

Jenkins applies the manifests, then runs `kubectl set image` with the exact ECR or Docker Hub image. Retrieve the external address with:

```bash
kubectl -n production get service admission-web
kubectl -n production get pods
```

`k8s/ingress.yaml` is optional. Install an ingress controller and replace its example hostname before applying it.

## 9. Jenkins setup

Install Jenkins with these plugins: Pipeline, Git, Credentials Binding, AWS Credentials, Docker Pipeline, and Kubernetes CLI support. The Jenkins agent needs Docker, AWS CLI, Terraform, kubectl, Python 3, and permission to run Docker.

Create these credentials in Jenkins:

| ID | Type | Purpose |
|---|---|---|
| `aws-credentials` | AWS access key or IAM-backed credential | Terraform, ECR, EKS |
| `dockerhub-credentials` | Username with Docker Hub access token as password | Docker Hub option |
| `postgres-password` | Secret text | Creates the Kubernetes PostgreSQL secret |
| GitHub credential if required | SSH key or token | Private repository checkout |

Use an IAM role on the Jenkins host/agent when possible instead of long-lived AWS keys. The Jenkinsfile keeps credential IDs visible as configuration but never contains secret values.

Create a Pipeline job configured as `Pipeline script from SCM`, select Git, enter the GitHub repository URL, and choose the repository branch. Jenkins reads the root `Jenkinsfile`.

Parameters:

- `REGISTRY`: `ECR` or `DOCKER_HUB`.
- `ACTION`: `APPLY` or `DESTROY`.
- `RESOURCE_MODE`: `USE_EXISTING` or `RECREATE`.
- `CONFIRM_DESTRUCTIVE`: required for `DESTROY` and `RECREATE`.
- `DOCKERHUB_REPOSITORY`: used for Docker Hub pushes.

GitHub Actions is intentionally not the deployment system here. Jenkins is the single CI/CD owner to avoid two pipelines deploying the same environment.

## 10. GitHub webhook

1. Make Jenkins reachable from GitHub over HTTPS. Use a DNS name or a secure tunnel for a lab; do not expose an unauthenticated Jenkins instance.
2. In Jenkins, enable the GitHub hook trigger for GITScm polling on the Pipeline job.
3. In GitHub, open **Settings > Webhooks > Add webhook**.
4. Set **Payload URL** to `https://jenkins.example.com/github-webhook/`.
5. Select `application/json`, choose **Just the push event**, and activate the webhook.
6. Push a commit. GitHub sends the event to Jenkins, Jenkins checks out the branch, and the pipeline begins.
7. Check GitHub webhook **Recent deliveries** and Jenkins **Build Console** if it does not trigger.

Expected flow: push -> GitHub -> webhook -> Jenkins checkout -> tests -> image push -> Terraform -> EKS -> rollout verification.

## 11. IAM permissions

Use separate roles for Terraform/Jenkins and EKS nodes. The node role in this project receives only the standard worker, CNI, and ECR read-only policies. The EKS control-plane role receives the EKS cluster policy.

For a lab, the Jenkins/Terraform role needs scoped permissions for the resources in this project: VPC networking (VPC, subnet, route, internet gateway, security-group operations), IAM role/policy attachment operations for the named project roles, EKS cluster/node-group operations, ECR repository and image push actions, and `sts:GetCallerIdentity`. Restrict resources by ARN and tag in a real account. EKS access also requires an EKS access entry or access mapping for the Jenkins principal so `aws eks update-kubeconfig` and kubectl operations are authorized.

Do not use `AdministratorAccess` by default. Start with the AWS managed policies needed for the lab, then replace them with a custom least-privilege policy scoped to this project and account. Review IAM Access Analyzer and CloudTrail after setup.

## 12. Security considerations

- Secrets are supplied by Jenkins Credentials, Kubernetes Secrets, AWS IAM roles, or local environment files.
- Real `.env`, Terraform state, plan files, cloud keys, tokens, and passwords are ignored by Git.
- The upload endpoint validates extension and size and generates a server-side filename.
- Use HTTPS, authentication/rate limiting, malware scanning, and private object storage for real document handling.
- The practice PostgreSQL pod and public subnets are not a production data architecture.
- Pin and regularly update dependencies, scan images, enable ECR scanning, and add network policies before production.

## 13. Troubleshooting

**Jenkins does not trigger:** inspect the GitHub webhook delivery, confirm the payload URL ends in `/github-webhook/`, and verify the Jenkins job trigger.

**ECR push fails:** verify the AWS credential binding, region, ECR repository, and ECR permissions. Check that Docker is logged into the account registry.

**Docker Hub push fails:** verify the repository parameter and that the credential password is an access token, not an account password.

**Terraform wants to recreate everything:** check that the same backend, workspace, region, variable values, and state are being used. Import existing resources if they were created outside Terraform.

**Pods do not start:** run `kubectl -n production describe pod <pod>` and inspect events. Confirm the image is public or configure an image pull secret. Check the PostgreSQL pod and the `DATABASE_URL` secret.

**LoadBalancer has no address:** wait for AWS provisioning and inspect `kubectl -n production describe service admission-web`.

## 14. Cleanup

From Jenkins, select `ACTION=DESTROY` and set `CONFIRM_DESTRUCTIVE=true` only after reviewing the target state. Locally:

```bash
cd terraform
terraform destroy
```

Destroying the Terraform stack does not automatically delete an external Docker Hub image. ECR is configured with `force_delete=false`, so remove images first if you intentionally want to delete the repository.
