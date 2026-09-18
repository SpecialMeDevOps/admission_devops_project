pipeline {
  agent any

  options {
    timestamps()
    skipDefaultCheckout(true)
    disableConcurrentBuilds()
  }

  parameters {
    choice(name: 'REGISTRY', choices: ['ECR', 'DOCKER_HUB'], description: 'Where the image will be pushed.')
    choice(name: 'ACTION', choices: ['APPLY', 'DESTROY'], description: 'Apply the stack or destroy it.')
    choice(name: 'RESOURCE_MODE', choices: ['USE_EXISTING', 'RECREATE'], description: 'USE_EXISTING keeps Terraform state and applies only changes. RECREATE requires confirmation.')
    booleanParam(name: 'CONFIRM_DESTRUCTIVE', defaultValue: false, description: 'Required for DESTROY or RECREATE.')
    string(name: 'DOCKERHUB_REPOSITORY', defaultValue: 'your-dockerhub-user/admission-api', description: 'Docker Hub repository, used only when DOCKER_HUB is selected.')
  }

  environment {
    AWS_REGION = 'us-east-1'
    TERRAFORM_VERSION = '1.10.5'
    AWS_CLI_VERSION = '2.22.35'
    KUBECTL_VERSION = '1.31.4'
    CLUSTER_NAME = 'admission-eks'
    ECR_REPOSITORY = 'admission-api'
    IMAGE_NAME = 'admission-api'
    AWS_ACCESS_KEY_CREDENTIAL_ID = 'aws-access-key-id'
    AWS_SECRET_KEY_CREDENTIAL_ID = 'aws-secret-access-key'
    DOCKERHUB_CREDENTIALS_ID = 'dockerhub-creds'
    POSTGRES_CREDENTIALS_ID = 'POSTGRES_PASSWORD'
    TERRAFORM_DIR = 'terraform'
    K8S_NAMESPACE = 'production'
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Prepare Terraform') {
      steps {
        sh '''
          set -eu
          mkdir -p "$WORKSPACE/.tools"
          if command -v terraform >/dev/null 2>&1; then
            ln -sf "$(command -v terraform)" "$WORKSPACE/.tools/terraform"
          else
            python3 - "$WORKSPACE/.tools" "$TERRAFORM_VERSION" <<'PY'
import sys
import urllib.request
import zipfile
from pathlib import Path

tools_dir = Path(sys.argv[1])
version = sys.argv[2]
archive = tools_dir / "terraform.zip"
url = f"https://releases.hashicorp.com/terraform/{version}/terraform_{version}_linux_amd64.zip"
urllib.request.urlretrieve(url, archive)
with zipfile.ZipFile(archive) as bundle:
    bundle.extract("terraform", tools_dir)
archive.unlink()
(tools_dir / "terraform").chmod(0o755)
PY
          fi
          "$WORKSPACE/.tools/terraform" version
        '''
      }
    }

    stage('Prepare Cloud Tools') {
      steps {
        sh '''
          set -eu
          mkdir -p "$WORKSPACE/.tools"

          if command -v aws >/dev/null 2>&1; then
            ln -sf "$(command -v aws)" "$WORKSPACE/.tools/aws"
          else
            python3 - "$WORKSPACE/.tools" "$AWS_CLI_VERSION" <<'PY'
import sys
import shutil
import urllib.request
import zipfile
from pathlib import Path

tools_dir = Path(sys.argv[1])
version = sys.argv[2]
archive = tools_dir / "awscliv2.zip"
install_dir = tools_dir / "aws-cli"
archive_dir = tools_dir / "aws-cli-archive"
url = f"https://awscli.amazonaws.com/awscli-exe-linux-x86_64-{version}.zip"
urllib.request.urlretrieve(url, archive)
shutil.rmtree(archive_dir, ignore_errors=True)
shutil.rmtree(install_dir, ignore_errors=True)
with zipfile.ZipFile(archive) as bundle:
  bundle.extractall(archive_dir)
archive.unlink()
archive_root = tools_dir / "aws-cli-archive" / "aws"
archive_root.rename(install_dir)
(tools_dir / "aws").unlink(missing_ok=True)
aws_binary = install_dir / "dist" / "aws"
aws_binary.chmod(0o755)
(tools_dir / "aws").symlink_to(aws_binary)
PY
          fi

          if command -v kubectl >/dev/null 2>&1; then
            ln -sf "$(command -v kubectl)" "$WORKSPACE/.tools/kubectl"
          else
            python3 - "$WORKSPACE/.tools" "$KUBECTL_VERSION" <<'PY'
import sys
import urllib.request
from pathlib import Path

tools_dir = Path(sys.argv[1])
version = sys.argv[2]
target = tools_dir / "kubectl"
urllib.request.urlretrieve(
    f"https://dl.k8s.io/release/v{version}/bin/linux/amd64/kubectl",
    target,
)
target.chmod(0o755)
PY
          fi

          chmod 755 "$WORKSPACE/.tools/aws" "$WORKSPACE/.tools/kubectl"
          "$WORKSPACE/.tools/aws" --version
          "$WORKSPACE/.tools/kubectl" version --client
        '''
      }
    }

    stage('Install Dependencies') {
      when { expression { params.ACTION == 'APPLY' } }
      steps {
        sh 'python3 -m venv .venv && . .venv/bin/activate && pip install --upgrade pip && pip install -r app/backend/requirements.txt'
      }
    }

    stage('Test') {
      when { expression { params.ACTION == 'APPLY' } }
      steps { sh '. .venv/bin/activate && PYTHONPATH="$WORKSPACE" pytest -q' }
    }

    stage('Docker Build') {
      when { expression { params.ACTION == 'APPLY' } }
      steps { sh 'docker build --tag ${IMAGE_NAME}:${BUILD_NUMBER} .' }
    }

    stage('Terraform ECR Bootstrap') {
      when {
        expression {
          params.ACTION == 'APPLY' && params.REGISTRY == 'ECR'
        }
      }
      steps {
        dir(env.TERRAFORM_DIR) {
          withCredentials([
            string(
              credentialsId: env.AWS_ACCESS_KEY_CREDENTIAL_ID,
              variable: 'AWS_ACCESS_KEY_ID'
            ),
            string(
              credentialsId: env.AWS_SECRET_KEY_CREDENTIAL_ID,
              variable: 'AWS_SECRET_ACCESS_KEY'
            )
          ]) {
            sh '''
              "$WORKSPACE/.tools/terraform" init -input=false
              "$WORKSPACE/.tools/terraform" apply -input=false -auto-approve \
                -target=module.ecr.aws_ecr_repository.this \
                -var="aws_region=${AWS_REGION}" \
                -var="cluster_name=${CLUSTER_NAME}"
            '''
          }
        }
      }
    }

    stage('Docker Image Tag') {
      when { expression { params.ACTION == 'APPLY' } }
      steps {
        script {
          if (params.REGISTRY == 'ECR') {
            withCredentials([
              string(credentialsId: env.AWS_ACCESS_KEY_CREDENTIAL_ID, variable: 'AWS_ACCESS_KEY_ID'),
              string(credentialsId: env.AWS_SECRET_KEY_CREDENTIAL_ID, variable: 'AWS_SECRET_ACCESS_KEY')
            ]) {
              env.ECR_REGISTRY = sh(script: '"$WORKSPACE/.tools/aws" sts get-caller-identity --query Account --output text', returnStdout: true).trim() + ".dkr.ecr.${AWS_REGION}.amazonaws.com"
            }
            env.IMAGE_URI = "${env.ECR_REGISTRY}/${env.ECR_REPOSITORY}:${env.BUILD_NUMBER}"
          } else {
            env.IMAGE_URI = "${params.DOCKERHUB_REPOSITORY}:${env.BUILD_NUMBER}"
          }
          sh 'docker tag ${IMAGE_NAME}:${BUILD_NUMBER} ${IMAGE_URI}'
        }
      }
    }

    stage('Login to Registry') {
      when { expression { params.ACTION == 'APPLY' } }
      steps {
        script {
          if (params.REGISTRY == 'ECR') {
            withCredentials([
              string(credentialsId: env.AWS_ACCESS_KEY_CREDENTIAL_ID, variable: 'AWS_ACCESS_KEY_ID'),
              string(credentialsId: env.AWS_SECRET_KEY_CREDENTIAL_ID, variable: 'AWS_SECRET_ACCESS_KEY')
            ]) {
              sh '"$WORKSPACE/.tools/aws" ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}'
            }
          } else {
            withCredentials([usernamePassword(credentialsId: env.DOCKERHUB_CREDENTIALS_ID, usernameVariable: 'DOCKERHUB_USER', passwordVariable: 'DOCKERHUB_TOKEN')]) {
              sh 'echo "${DOCKERHUB_TOKEN}" | docker login --username "${DOCKERHUB_USER}" --password-stdin'
            }
          }
        }
      }
    }

    stage('Push Docker Image') {
      when { expression { params.ACTION == 'APPLY' } }
      steps { sh 'docker push ${IMAGE_URI}' }
    }

    stage('Terraform Init') {
      steps {
        dir(env.TERRAFORM_DIR) {
          withCredentials([
            string(credentialsId: env.AWS_ACCESS_KEY_CREDENTIAL_ID, variable: 'AWS_ACCESS_KEY_ID'),
            string(credentialsId: env.AWS_SECRET_KEY_CREDENTIAL_ID, variable: 'AWS_SECRET_ACCESS_KEY')
          ]) {
            sh '"$WORKSPACE/.tools/terraform" init -input=false'
          }
        }
      }
    }

    stage('Terraform Plan') {
      when { expression { params.ACTION == 'APPLY' } }
      steps {
        dir(env.TERRAFORM_DIR) {
          withCredentials([
            string(credentialsId: env.AWS_ACCESS_KEY_CREDENTIAL_ID, variable: 'AWS_ACCESS_KEY_ID'),
            string(credentialsId: env.AWS_SECRET_KEY_CREDENTIAL_ID, variable: 'AWS_SECRET_ACCESS_KEY')
          ]) {
            sh '"$WORKSPACE/.tools/terraform" plan -input=false -out=tfplan -var="aws_region=${AWS_REGION}" -var="cluster_name=${CLUSTER_NAME}"'
          }
        }
      }
    }

    stage('Terraform Apply') {
      when { expression { params.ACTION == 'APPLY' } }
      steps {
        script {
          if (params.RESOURCE_MODE == 'RECREATE' && !params.CONFIRM_DESTRUCTIVE) {
            error('RECREATE requires CONFIRM_DESTRUCTIVE=true. Review the Terraform plan first.')
          }
        }
        dir(env.TERRAFORM_DIR) {
          withCredentials([
            string(credentialsId: env.AWS_ACCESS_KEY_CREDENTIAL_ID, variable: 'AWS_ACCESS_KEY_ID'),
            string(credentialsId: env.AWS_SECRET_KEY_CREDENTIAL_ID, variable: 'AWS_SECRET_ACCESS_KEY')
          ]) {
            sh '"$WORKSPACE/.tools/terraform" apply -input=false -auto-approve tfplan'
          }
        }
      }
    }

    stage('Terraform Destroy') {
      when { expression { params.ACTION == 'DESTROY' } }
      steps {
        script {
          if (!params.CONFIRM_DESTRUCTIVE) {
            error('DESTROY requires CONFIRM_DESTRUCTIVE=true. Re-run only after reviewing the target workspace and state.')
          }
        }
        dir(env.TERRAFORM_DIR) {
          withCredentials([
            string(credentialsId: env.AWS_ACCESS_KEY_CREDENTIAL_ID, variable: 'AWS_ACCESS_KEY_ID'),
            string(credentialsId: env.AWS_SECRET_KEY_CREDENTIAL_ID, variable: 'AWS_SECRET_ACCESS_KEY')
          ]) {
            sh '"$WORKSPACE/.tools/terraform" destroy -input=false -auto-approve -var="aws_region=${AWS_REGION}" -var="cluster_name=${CLUSTER_NAME}"'
          }
        }
      }
    }

    stage('Kubernetes Deployment') {
      when { expression { params.ACTION == 'APPLY' } }
      steps {
        withCredentials([
          string(
            credentialsId: env.AWS_ACCESS_KEY_CREDENTIAL_ID,
            variable: 'AWS_ACCESS_KEY_ID'
          ),
          string(
            credentialsId: env.AWS_SECRET_KEY_CREDENTIAL_ID,
            variable: 'AWS_SECRET_ACCESS_KEY'
          ),
          string(
            credentialsId: env.POSTGRES_CREDENTIALS_ID,
            variable: 'POSTGRES_PASSWORD'
          )
        ]) {
          sh '''
            set +x
            "$WORKSPACE/.tools/aws" eks update-kubeconfig --region "${AWS_REGION}" --name "${CLUSTER_NAME}"
            "$WORKSPACE/.tools/kubectl" apply -f k8s/namespace.yaml
            "$WORKSPACE/.tools/kubectl" apply -f k8s/configmap.yaml
            "$WORKSPACE/.tools/kubectl" create secret generic admission-secrets --namespace "${K8S_NAMESPACE}" \\
              --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \\
              --from-literal=DATABASE_URL="postgresql://admission:${POSTGRES_PASSWORD}@postgres:5432/admission" \\
              --dry-run=client -o yaml | "$WORKSPACE/.tools/kubectl" apply -f -
            "$WORKSPACE/.tools/kubectl" apply -f k8s/postgres.yaml
            "$WORKSPACE/.tools/kubectl" apply -f k8s/deployment.yaml
            "$WORKSPACE/.tools/kubectl" apply -f k8s/service.yaml
            "$WORKSPACE/.tools/kubectl" -n "${K8S_NAMESPACE}" set image deployment/admission-web admission-web="${IMAGE_URI}"
          '''
        }
      }
    }

    stage('Verify Deployment') {
      when { expression { params.ACTION == 'APPLY' } }
      steps {
        withCredentials([
          string(
            credentialsId: env.AWS_ACCESS_KEY_CREDENTIAL_ID,
            variable: 'AWS_ACCESS_KEY_ID'
          ),
          string(
            credentialsId: env.AWS_SECRET_KEY_CREDENTIAL_ID,
            variable: 'AWS_SECRET_ACCESS_KEY'
          )
        ]) {
          sh '''
            set -eu
            export PATH="$WORKSPACE/.tools:$PATH"
            if ! "$WORKSPACE/.tools/kubectl" -n "${K8S_NAMESPACE}" rollout status deployment/postgres --timeout=180s; then
              "$WORKSPACE/.tools/kubectl" -n "${K8S_NAMESPACE}" get pods,pvc,events --sort-by=.lastTimestamp || true
              "$WORKSPACE/.tools/kubectl" -n "${K8S_NAMESPACE}" describe deployment/postgres || true
              "$WORKSPACE/.tools/kubectl" -n "${K8S_NAMESPACE}" logs deployment/postgres --all-containers=true --tail=100 || true
              exit 1
            fi
            "$WORKSPACE/.tools/kubectl" -n "${K8S_NAMESPACE}" rollout status deployment/admission-web --timeout=180s
            "$WORKSPACE/.tools/kubectl" -n "${K8S_NAMESPACE}" get pods -l app=admission-web -o wide
            "$WORKSPACE/.tools/kubectl" -n "${K8S_NAMESPACE}" get service admission-web
          '''
        }
      }
    }
  }

  post {
    always { sh 'rm -rf .venv || true' }
  }
}
