import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as targets from 'aws-cdk-lib/aws-route53-targets';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';

export interface MailboxImageAnalyzerStackProps extends cdk.StackProps {
  environment: 'dev' | 'prod';
}

export class MailboxImageAnalyzerStack extends cdk.Stack {
  public readonly imageBucket: s3.Bucket;
  public readonly cloudfrontDistribution: cloudfront.Distribution;

  constructor(scope: Construct, id: string, props: MailboxImageAnalyzerStackProps) {
    super(scope, id, props);

    // Create S3 bucket for storing mailbox images and hosting webapp
    this.imageBucket = new s3.Bucket(this, 'MailboxImageBucket', {
      bucketName: `mailbox-image-analyzer-${props.environment}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ACLS,
      removalPolicy: props.environment === 'prod' 
        ? cdk.RemovalPolicy.RETAIN 
        : cdk.RemovalPolicy.DESTROY,
      websiteIndexDocument: 'index.html',
      websiteErrorDocument: 'index.html',
      lifecycleRules: [
        {
          id: 'DeleteOldImages',
          enabled: true,
          noncurrentVersionExpiration: cdk.Duration.days(30),
          expiration: cdk.Duration.days(365), // Keep images for 1 year
        },
      ],
    });

    // Add bucket policy for secure access and public webapp access
    this.imageBucket.addToResourcePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.DENY,
        principals: [new iam.AnyPrincipal()],
        actions: ['s3:*'],
        resources: [this.imageBucket.arnForObjects('*')],
        conditions: {
          Bool: {
            'aws:SecureTransport': 'false',
          },
        },
      })
    );

    // Allow public read access to webapp files (HTML, CSS, JS)
    this.imageBucket.addToResourcePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        principals: [new iam.AnyPrincipal()],
        actions: ['s3:GetObject'],
        resources: [
          this.imageBucket.arnForObjects('*.html'),
          this.imageBucket.arnForObjects('*.css'),
          this.imageBucket.arnForObjects('*.js'),
          this.imageBucket.arnForObjects('*.png'),
          this.imageBucket.arnForObjects('*.jpg'),
          this.imageBucket.arnForObjects('*.jpeg'),
          this.imageBucket.arnForObjects('*.gif'),
          this.imageBucket.arnForObjects('*.svg'),
          this.imageBucket.arnForObjects('*.ico'),
        ],
      })
    );

    // Output the bucket name
    new cdk.CfnOutput(this, 'ImageBucketName', {
      value: this.imageBucket.bucketName,
      description: 'Name of the S3 bucket for mailbox images',
      exportName: `MailboxImageBucketName-${props.environment}`,
    });

    // Deploy webapp files to the same S3 bucket
    new s3deploy.BucketDeployment(this, 'WebappDeployment', {
      sources: [s3deploy.Source.asset('../webapp')],
      destinationBucket: this.imageBucket,
      destinationKeyPrefix: '', // Upload to root of bucket
    });

    // Get the hosted zone for g103.net
    const hostedZone = route53.HostedZone.fromLookup(this, 'HostedZone', {
      domainName: 'g103.net',
    });

    // Create domain name based on environment
    const domainName = props.environment === 'dev' 
      ? 'mailbox-dev.g103.net' 
      : 'mailbox.g103.net';

    // Create SSL certificate for the domain
    const certificate = new acm.Certificate(this, 'Certificate', {
      domainName: domainName,
      validation: acm.CertificateValidation.fromDns(hostedZone),
    });

    // Create CloudFront distribution
    this.cloudfrontDistribution = new cloudfront.Distribution(this, 'Distribution', {
      defaultBehavior: {
        origin: new origins.S3Origin(this.imageBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      domainNames: [domainName],
      certificate: certificate,
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
        },
      ],
    });

    // Create DNS record pointing to CloudFront
    new route53.ARecord(this, 'AliasRecord', {
      zone: hostedZone,
      recordName: props.environment === 'dev' ? 'mailbox-dev' : 'mailbox',
      target: route53.RecordTarget.fromAlias(
        new targets.CloudFrontTarget(this.cloudfrontDistribution)
      ),
    });

    // Output the bucket ARN
    new cdk.CfnOutput(this, 'ImageBucketArn', {
      value: this.imageBucket.bucketArn,
      description: 'ARN of the S3 bucket for mailbox images',
      exportName: `MailboxImageBucketArn-${props.environment}`,
    });

    // Output the website URL
    new cdk.CfnOutput(this, 'WebsiteUrl', {
      value: this.imageBucket.bucketWebsiteUrl,
      description: 'URL of the webapp website',
      exportName: `WebsiteUrl-${props.environment}`,
    });

    // Output the custom domain URL
    new cdk.CfnOutput(this, 'CustomDomainUrl', {
      value: `https://${domainName}`,
      description: 'Custom domain URL for the webapp',
      exportName: `CustomDomainUrl-${props.environment}`,
    });

    // Output the CloudFront distribution URL
    new cdk.CfnOutput(this, 'CloudFrontUrl', {
      value: this.cloudfrontDistribution.distributionDomainName,
      description: 'CloudFront distribution URL',
      exportName: `CloudFrontUrl-${props.environment}`,
    });
  }
}
