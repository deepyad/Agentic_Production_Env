# Infrastructure — Docker & Kubernetes

Docker and Kubernetes assets for the Agentic Production Framework API.

## Layout

```
infra/
├── docker/
│   ├── Dockerfile
│   └── .dockerignore
├── kubernetes/
│   ├── base/
│   │   └── kustomization.yaml
│   ├── overlays/
│   │   └── azure/
│   │       └── kustomization.yaml   # ACR image for Azure
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── hpa.yaml
│   ├── ingress.yaml
│   └── kustomization.yaml
├── scripts/
│   ├── build.sh
│   ├── deploy.sh
│   ├── create-secret-from-env.sh
│   ├── azure-build-push.sh          # Build + push to ACR
│   └── azure-deploy.sh               # Deploy to AKS (Azure overlay)
└── README.md (this file)
```

## Docker

### Build (from project root)

```bash
docker build -t agentic-api:latest -f infra/docker/Dockerfile .
```

Or use the script:

```bash
./infra/scripts/build.sh
# Or with custom tag: IMAGE_TAG=v1.0 ./infra/scripts/build.sh
```

### Run locally

```bash
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -e MCP_SERVER_URL=http://host.docker.internal:3000/mcp \
  agentic-api:latest
```

## Kubernetes

### Prerequisites

- `kubectl` configured for your cluster
- Docker image available to the cluster (push to a registry or use kind/minikube load)

### 1. Create secret (required)

Set `OPENAI_API_KEY` and optionally `MCP_SERVER_URL`, then:

```bash
./infra/scripts/create-secret-from-env.sh
```

Or edit `infra/kubernetes/secret.yaml` and replace `REPLACE_ME` (prefer a secret manager in production).

### 2. Deploy

From project root:

```bash
kubectl apply -k infra/kubernetes
```

Or:

```bash
./infra/scripts/deploy.sh
```

### 3. Use a registry image

Edit `infra/kubernetes/deployment.yaml` and set:

```yaml
image: your-registry.io/agentic-api:latest
imagePullPolicy: Always
```

Then build and push:

```bash
docker build -t your-registry.io/agentic-api:latest -f infra/docker/Dockerfile .
docker push your-registry.io/agentic-api:latest
```

### 4. Check

```bash
kubectl get pods -n agentic
kubectl get svc -n agentic
kubectl logs -n agentic -l app=agentic-api -f
```

### Optional: Ingress

Uncomment `ingress.yaml` in `infra/kubernetes/kustomization.yaml`, set `host` in `ingress.yaml`, then apply. Ensure an Ingress controller (e.g. nginx) is installed.

## Config

- **ConfigMap** (`configmap.yaml`): non-sensitive env (model, thresholds, feature flags). Edit and re-apply to change.
- **Secret** (`secret.yaml`): `OPENAI_API_KEY`, `MCP_SERVER_URL`. Use `create-secret-from-env.sh` or a secret manager.

## HPA

Horizontal Pod Autoscaler scales the API deployment between 2 and 10 replicas on CPU (70%) and memory (80%). Adjust in `hpa.yaml`.

---

## Deploy to Azure (AKS + ACR)

### Prerequisites

- **Azure CLI** (`az`) logged in: `az login`
- **kubectl** and context pointing to your **AKS** cluster: `az aks get-credentials --resource-group <RG> --name <AKS_NAME>`
- **Docker** (or Podman) for building images

### 1. Create Azure Container Registry (if you don’t have one)

```bash
RESOURCE_GROUP=myResourceGroup
ACR_NAME=myagenticacr   # must be globally unique, 5–50 alphanumeric
LOCATION=eastus

az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic
```

### 2. Let AKS pull from ACR

Attach the registry to the cluster so it can pull images without extra secrets:

```bash
AKS_NAME=myAKSCluster
az aks update --resource-group $RESOURCE_GROUP --name $AKS_NAME --attach-acr $ACR_NAME
```

### 3. Create Kubernetes secret

From project root, with `.env` or env vars set:

```bash
./infra/scripts/create-secret-from-env.sh
```

### 4. Build and push image to ACR

From project root (replace `myagenticacr` with your ACR name):

```bash
./infra/scripts/azure-build-push.sh myagenticacr latest
```

This builds the image, tags it as `myagenticacr.azurecr.io/agentic-api:latest`, and pushes to ACR.

### 5. Deploy to AKS

```bash
./infra/scripts/azure-deploy.sh myagenticacr latest
```

This applies the Azure overlay (ACR image) to the current cluster. Verify:

```bash
kubectl get pods -n agentic
kubectl get svc -n agentic
```

### 6. Optional: expose via Load Balancer or Ingress

- **Quick test:** change the Service to `type: LoadBalancer` in `infra/kubernetes/service.yaml` (or use a patch in the overlay), then get the external IP with `kubectl get svc -n agentic`.
- **Production:** use an [Application Gateway Ingress Controller (AGIC)](https://learn.microsoft.com/en-us/azure/application-gateway/ingress-controller-overview) or an nginx Ingress with an Azure Load Balancer.

### Files used for Azure

- **Overlay:** `infra/kubernetes/overlays/azure/kustomization.yaml` — sets the deployment image to `YOUR_ACR_NAME.azurecr.io/agentic-api:latest`. The scripts replace `YOUR_ACR_NAME` when you run them; you can also edit the file manually.
- **Base:** `infra/kubernetes/base/` — shared resources; the default `kubectl apply -k infra/kubernetes` uses this.
