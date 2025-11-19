#!/bin/bash

# SafeTradeLab Kubernetes Cleanup Script
# This script removes all Kubernetes resources

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="safetradelab"

echo -e "${YELLOW}======================================${NC}"
echo -e "${YELLOW}SafeTradeLab Kubernetes Cleanup${NC}"
echo -e "${YELLOW}======================================${NC}"

# Check if namespace exists
if ! kubectl get namespace $NAMESPACE &> /dev/null; then
    echo -e "${GREEN}Namespace $NAMESPACE does not exist. Nothing to clean up.${NC}"
    exit 0
fi

# Show current resources
echo -e "\n${YELLOW}Current resources in namespace $NAMESPACE:${NC}"
kubectl get all -n $NAMESPACE

# Confirmation
echo -e "\n${RED}WARNING: This will delete all resources in namespace $NAMESPACE${NC}"
read -p "Are you sure you want to continue? (yes/no): " -r
echo

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${GREEN}Cleanup cancelled${NC}"
    exit 0
fi

# Delete namespace (this will delete all resources in it)
echo -e "\n${YELLOW}Deleting namespace $NAMESPACE...${NC}"
kubectl delete namespace $NAMESPACE

echo -e "\n${GREEN}======================================${NC}"
echo -e "${GREEN}Cleanup Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}All resources have been deleted.${NC}\n"
