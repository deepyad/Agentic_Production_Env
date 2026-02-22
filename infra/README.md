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

## Kubernetes manifests explained

Each YAML file under `kubernetes/` has a specific role. Kustomize ties them together so you can deploy with one command.

| File | Kind | Purpose |
|------|------|---------|
| **namespace.yaml** | Namespace | Creates the `agentic` namespace. All other resources (Deployment, Service, etc.) live in this namespace so they are isolated from other apps in the cluster. |
| **configmap.yaml** | ConfigMap | Holds **non-sensitive** app config as key-value pairs: `DEFAULT_MODEL`, `HALLUCINATION_THRESHOLD_*`, `TOP_P`, `GUARDRAILS_ENABLED`, `USE_TF_*`, optional Weaviate URL/index. The Deployment injects these into the container as environment variables via `envFrom`. Edit and re-apply to change behaviour without rebuilding the image. |
| **secret.yaml** | Secret | Holds **sensitive** config: `OPENAI_API_KEY`, `MCP_SERVER_URL`. Injected into the container like the ConfigMap. Replace `REPLACE_ME` before deploy, or use `create-secret-from-env.sh` / a secret manager. Do not commit real keys. |
| **deployment.yaml** | Deployment | Defines the **API workload**: which image to run (`agentic-api:latest`), how many replicas (2), ports (8000), and env from ConfigMap + Secret. Sets **resource requests/limits** (memory 512Mi–1Gi, CPU 250m–1000m) for scheduling and for HPA. **Liveness probe** (`/health`) restarts the container if unhealthy; **readiness probe** (`/health`) keeps traffic off until the app is ready. |
| **service.yaml** | Service | Exposes the Deployment pods inside the cluster as a single **ClusterIP** (internal DNS name `agentic-api.agentic.svc.cluster.local:8000`). Other pods or an Ingress use this to send traffic to the API. **Selector** `app: agentic-api` matches the Deployment’s pods. |
| **hpa.yaml** | HorizontalPodAutoscaler | Scales the **agentic-api** Deployment based on CPU and memory. When average **CPU utilization** > 70% or **memory utilization** > 80%, HPA adds pods (up to **maxReplicas: 10**); when lower, it scales down to **minReplicas: 2**. Requires resource **requests** on the Deployment (so utilization % can be computed). |
| **ingress.yaml** | Ingress | **Optional.** Exposes the API to the outside world via HTTP(S). Uses **ingressClassName: nginx**; host `agentic-api.example.com` and path `/` route to the **agentic-api** service on port 8000. Uncomment TLS and cert-manager annotations for HTTPS. Not included in the default Kustomize base; add to your overlay if you use an Ingress controller. |
| **kustomization.yaml** (root) | Kustomization | Top-level Kustomize: sets **namespace: agentic** and includes the **base** directory. Run `kubectl apply -k infra/kubernetes` to deploy everything. |
| **base/kustomization.yaml** | Kustomization | Lists the actual resources: namespace, configmap, secret, deployment, service, hpa. Adds **commonLabels** to all resources. Ingress is not in the base so it stays optional. |

**Flow:** Namespace and config (ConfigMap + Secret) are created first; Deployment starts pods that read env from them; Service gives a stable endpoint to those pods; HPA adjusts replica count from CPU/memory. Ingress (if used) sends external traffic to the Service.

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
