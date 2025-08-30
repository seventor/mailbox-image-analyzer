#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { MailboxImageAnalyzerStack } from '../lib/mailbox-image-analyzer-stack';

const app = new cdk.App();

// Get environment from context or default to dev
const environment = app.node.tryGetContext('environment') || 'dev';

// Validate environment
if (!['dev', 'prod'].includes(environment)) {
  throw new Error('Environment must be either "dev" or "prod"');
}

// Create stack for the specified environment
new MailboxImageAnalyzerStack(app, `MailboxImageAnalyzerStack-${environment}`, {
  environment: environment as 'dev' | 'prod',
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  },
  description: `Mailbox Image Analyzer infrastructure for ${environment} environment`,
  tags: {
    Environment: environment,
    Project: 'mailbox-image-analyzer',
    ManagedBy: 'CDK',
  },
});
