#!/bin/bash

# SafeTradeLab Kubernetes Deployment Script
# This script deploys the data collector to Kubernetes

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="safetradelab"
K8S_DIR="k8s"

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}SafeTradeLab Kubernetes Deployment${NC}"
echo -e "${GREEN}======================================${NC}"

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}ERROR: kubectl is not installed${NC}"
    exit 1
fi

# Check if k8s directory exists
if [ ! -d "$K8S_DIR" ]; then
    echo -e "${RED}ERROR: k8s directory not found${NC}"
    exit 1
fi

# Function to wait for deployment
wait_for_deployment() {
    local deployment=$1
    local namespace=$2

    echo -e "${YELLOW}Waiting for $deployment to be ready...${NC}"
    kubectl wait --for=condition=available --timeout=300s deployment/$deployment -n $namespace
    echo -e "${GREEN}✓ $deployment is ready${NC}"
}

# Function to wait for pod
wait_for_pod() {
    local label=$1
    local namespace=$2

    echo -e "${YELLOW}Waiting for pod with label $label to be ready...${NC}"
    kubectl wait --for=condition=ready pod -l $label -n $namespace --timeout=300s
    echo -e "${GREEN}✓ Pod is ready${NC}"
}

# Step 1: Create namespace
echo -e "\n${YELLOW}Step 1: Creating namespace...${NC}"
kubectl apply -f $K8S_DIR/namespace.yaml
echo -e "${GREEN}✓ Namespace created${NC}"

# Step 2: Create ConfigMap and Secrets
echo -e "\n${YELLOW}Step 2: Creating ConfigMap and Secrets...${NC}"
kubectl apply -f $K8S_DIR/configmap.yaml
kubectl apply -f $K8S_DIR/secret.yaml
echo -e "${GREEN}✓ ConfigMap and Secrets created${NC}"

# Step 3: Deploy PostgreSQL
echo -e "\n${YELLOW}Step 3: Deploying PostgreSQL...${NC}"
kubectl apply -f $K8S_DIR/postgres-pvc.yaml
kubectl apply -f $K8S_DIR/postgres-deployment.yaml

# Wait for PostgreSQL to be ready
wait_for_pod "app=postgres" $NAMESPACE

# Step 4: Deploy Data Collector
echo -e "\n${YELLOW}Step 4: Deploying Data Collector...${NC}"
kubectl apply -f $K8S_DIR/datacollector-deployment.yaml

# Wait for Data Collector to be ready
wait_for_deployment "datacollector" $NAMESPACE

# Step 5: Show status
echo -e "\n${GREEN}======================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}======================================${NC}"

echo -e "\n${YELLOW}Current Status:${NC}"
kubectl get all -n $NAMESPACE

echo -e "\n${YELLOW}Useful Commands:${NC}"
echo -e "  View logs:           ${GREEN}kubectl logs -f deployment/datacollector -n $NAMESPACE${NC}"
echo -e "  View PostgreSQL logs: ${GREEN}kubectl logs -f deployment/postgres -n $NAMESPACE${NC}"
echo -e "  Check pods:          ${GREEN}kubectl get pods -n $NAMESPACE${NC}"
echo -e "  Describe pod:        ${GREEN}kubectl describe pod <pod-name> -n $NAMESPACE${NC}"
echo -e "  Shell into pod:      ${GREEN}kubectl exec -it deployment/datacollector -n $NAMESPACE -- /bin/bash${NC}"
echo -e "  Delete all:          ${GREEN}kubectl delete namespace $NAMESPACE${NC}"

echo -e "\n${GREEN}✓ All done!${NC}\n"
