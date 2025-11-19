#!/bin/bash

# Docker Build and Push Script
# Supports both AWS ECR and Docker Hub

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Docker Build and Push Script${NC}"
echo -e "${GREEN}======================================${NC}"

# Ask for registry type
echo -e "\n${YELLOW}Select registry type:${NC}"
echo "1) AWS ECR"
echo "2) Docker Hub"
read -p "Enter choice (1 or 2): " registry_choice

if [ "$registry_choice" = "1" ]; then
    # AWS ECR
    echo -e "\n${YELLOW}AWS ECR Configuration${NC}"
    read -p "Enter AWS Account ID: " aws_account_id
    read -p "Enter AWS Region (e.g., us-east-1): " aws_region
    read -p "Enter Repository Name (default: safetradelab/datacollector): " repo_name
    repo_name=${repo_name:-safetradelab/datacollector}

    ECR_URL="$aws_account_id.dkr.ecr.$aws_region.amazonaws.com"
    FULL_IMAGE="$ECR_URL/$repo_name:latest"

    echo -e "\n${YELLOW}Logging in to AWS ECR...${NC}"
    aws ecr get-login-password --region $aws_region | docker login --username AWS --password-stdin $ECR_URL

    echo -e "\n${YELLOW}Creating ECR repository if it doesn't exist...${NC}"
    aws ecr create-repository --repository-name $repo_name --region $aws_region 2>/dev/null || echo "Repository already exists"

elif [ "$registry_choice" = "2" ]; then
    # Docker Hub
    echo -e "\n${YELLOW}Docker Hub Configuration${NC}"
    read -p "Enter Docker Hub username: " docker_username
    read -p "Enter repository name (default: datacollector): " repo_name
    repo_name=${repo_name:-datacollector}

    FULL_IMAGE="$docker_username/$repo_name:latest"

    echo -e "\n${YELLOW}Logging in to Docker Hub...${NC}"
    docker login

else
    echo -e "${RED}Invalid choice${NC}"
    exit 1
fi

# Build Docker image
echo -e "\n${YELLOW}Building Docker image...${NC}"
docker build -t safetradelab/datacollector:latest .
echo -e "${GREEN}✓ Image built successfully${NC}"

# Tag image
echo -e "\n${YELLOW}Tagging image as $FULL_IMAGE...${NC}"
docker tag safetradelab/datacollector:latest $FULL_IMAGE
echo -e "${GREEN}✓ Image tagged successfully${NC}"

# Push image
echo -e "\n${YELLOW}Pushing image to registry...${NC}"
docker push $FULL_IMAGE
echo -e "${GREEN}✓ Image pushed successfully${NC}"

# Summary
echo -e "\n${GREEN}======================================${NC}"
echo -e "${GREEN}Build and Push Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo -e "\n${YELLOW}Image URL:${NC} ${GREEN}$FULL_IMAGE${NC}"
echo -e "\n${YELLOW}Next Steps:${NC}"
echo -e "1. Update ${GREEN}k8s/datacollector-deployment.yaml${NC} with the image URL:"
echo -e "   ${GREEN}image: $FULL_IMAGE${NC}"
echo -e "2. Deploy to Kubernetes:"
echo -e "   ${GREEN}./scripts/deploy-k8s.sh${NC}"
echo -e ""
