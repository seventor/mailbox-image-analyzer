# Mailbox Image Analyzer

A CDK-based infrastructure for analyzing images captured by a camera inside a mailbox.

## Project Overview

This project creates AWS infrastructure for a mailbox image analyzer application with the following components:

- **S3 Buckets**: Secure storage for mailbox images with environment-specific buckets
- **Lambda Functions**: Serverless functions for image processing (to be implemented)
- **Web Application**: Simple web interface for viewing images (to be implemented)

## Infrastructure

### S3 Buckets

The CDK stack creates S3 buckets with the following naming convention:
- Development: `mailbox-image-analyzer-dev`
- Production: `mailbox-image-analyzer-prod`

### Security Features

- **Encryption**: S3-managed encryption enabled
- **Public Access**: All public access blocked
- **Versioning**: Enabled for data protection
- **Lifecycle Rules**: Automatic cleanup of old images (1 year retention)
- **HTTPS Enforcement**: Denies non-HTTPS requests

## Prerequisites

Before deploying this infrastructure, ensure you have:

1. **AWS CLI** installed and configured
2. **Node.js** (version 16 or higher)
3. **AWS CDK** installed globally: `npm install -g aws-cdk`
4. **AWS credentials** configured for your target account

## Setup

1. **Install dependencies**:
   ```bash
   npm install
   npm run cdk:install
   ```

2. **Build the project**:
   ```bash
   npm run cdk:build
   ```

3. **Bootstrap CDK** (first time only):
   ```bash
   cd cdk && cdk bootstrap
   ```

## Deployment

### Using the Deployment Script (Recommended)

Deploy to development environment:
```bash
npm run deploy:dev
```

Deploy to production environment:
```bash
npm run deploy:prod
```

### Using CDK Commands Directly

Deploy to development:
```bash
cd cdk && cdk deploy --context environment=dev
```

Deploy to production:
```bash
cd cdk && cdk deploy --context environment=prod
```

### Using npm scripts

Deploy to development:
```bash
npm run cdk:deploy:dev
```

Deploy to production:
```bash
npm run cdk:deploy:prod
```

## Environment Differences

| Feature | Development | Production |
|---------|-------------|------------|
| Bucket Name | `mailbox-image-analyzer-dev` | `mailbox-image-analyzer-prod` |
| Removal Policy | Destroy | Retain |
| Stack Name | `MailboxImageAnalyzerStack-dev` | `MailboxImageAnalyzerStack-prod` |

## Cleanup

To destroy the infrastructure:

### Development
```bash
cd cdk && cdk destroy --context environment=dev
```

### Production
```bash
cd cdk && cdk destroy --context environment=prod
```

**Warning**: Production resources are set to RETAIN policy, so manual cleanup may be required.

## Development

### Project Structure

```
├── cdk/                          # CDK infrastructure
│   ├── bin/                      # CDK app entry point
│   │   └── mailbox-image-analyzer.ts
│   ├── lib/                      # CDK constructs
│   │   └── mailbox-image-analyzer-stack.ts
│   ├── scripts/                  # Deployment scripts
│   │   └── deploy.sh
│   ├── cdk.json                  # CDK configuration
│   ├── package.json              # CDK dependencies
│   └── tsconfig.json             # TypeScript configuration
├── package.json                  # Root project configuration
├── README.md                     # This file
└── instructions.md               # Project requirements
```

### Adding New Resources

To add new AWS resources to the stack:

1. Edit `cdk/lib/mailbox-image-analyzer-stack.ts`
2. Add the new resource to the stack
3. Build the project: `npm run cdk:build`
4. Deploy: `npm run deploy:[dev|prod]`

## Next Steps

1. **Lambda Functions**: Implement image processing functions
2. **Web Application**: Create a simple web interface for viewing images
3. **API Gateway**: Set up REST API for the web application
4. **CloudFront**: Add CDN for better performance
5. **Monitoring**: Add CloudWatch alarms and dashboards

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test the deployment
5. Submit a pull request

## License

This project is licensed under the MIT License.
