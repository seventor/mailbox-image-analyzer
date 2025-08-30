#!/bin/bash

# Mailbox Image Analyzer CDK Deployment Script
# Usage: ./scripts/deploy.sh [dev|prod]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if environment is provided
if [ $# -eq 0 ]; then
    print_error "Please specify environment: dev or prod"
    echo "Usage: $0 [dev|prod]"
    exit 1
fi

ENVIRONMENT=$1

# Validate environment
if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    print_error "Invalid environment. Must be 'dev' or 'prod'"
    exit 1
fi

print_status "Deploying to $ENVIRONMENT environment..."

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check if CDK is installed
if ! command -v cdk &> /dev/null; then
    print_error "AWS CDK is not installed. Please install it first: npm install -g aws-cdk"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "cdk.json" ]; then
    print_error "cdk.json not found. Please run this script from the cdk directory."
    exit 1
fi

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    print_status "Installing dependencies..."
    npm install
fi

# Build the project
print_status "Building the project..."
npm run build

# Bootstrap CDK if needed (only for first deployment)
print_status "Checking if CDK is bootstrapped..."
if ! cdk list &> /dev/null; then
    print_warning "CDK not bootstrapped. Bootstrapping now..."
    cdk bootstrap
fi

# Deploy the stack
print_status "Deploying CDK stack..."
cdk deploy --context environment=$ENVIRONMENT --require-approval never

print_status "Deployment completed successfully!"
print_status "Stack name: MailboxImageAnalyzerStack-$ENVIRONMENT"
print_status "S3 Bucket: mailbox-image-analyzer-$ENVIRONMENT"
