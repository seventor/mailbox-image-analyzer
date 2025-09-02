import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as route53Targets from 'aws-cdk-lib/aws-route53-targets';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as events from 'aws-cdk-lib/aws-events';
import * as eventTargets from 'aws-cdk-lib/aws-events-targets';

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
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL, // Block all public access for security
      removalPolicy: cdk.RemovalPolicy.RETAIN, // Keep data safe in both environments
      lifecycleRules: [
        {
          id: 'DeleteOldImages',
          enabled: true,
          noncurrentVersionExpiration: cdk.Duration.days(30),
          expiration: cdk.Duration.days(365), // Keep images for 1 year
        },
      ],
    });

    // Add bucket policy to require HTTPS
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

    // Output the bucket name
    new cdk.CfnOutput(this, 'ImageBucketName', {
      value: this.imageBucket.bucketName,
      description: 'Name of the S3 bucket for mailbox images',
      exportName: `MailboxImageBucketName-${props.environment}`,
    });



    // Get the hosted zone for g103.net
    const hostedZone = route53.HostedZone.fromLookup(this, 'HostedZone', {
      domainName: 'g103.net',
    });

    // Create domain name based on environment
    const domainName = props.environment === 'dev' 
      ? 'mailbox-dev.g103.net' 
      : 'mailbox.g103.net';

    // Create API subdomain
    const apiDomainName = props.environment === 'dev' 
      ? 'api.mailbox-dev.g103.net' 
      : 'api.mailbox.g103.net';

    // Create SSL certificate for the domain (including API subdomain)
    const certificate = new acm.Certificate(this, 'Certificate', {
      domainName: domainName,
      subjectAlternativeNames: [apiDomainName],
      validation: acm.CertificateValidation.fromDns(hostedZone),
    });

    // Configure S3 origin using Origin Access Control (OAC)
    const s3Origin = origins.S3BucketOrigin.withOriginAccessControl(this.imageBucket, {
      // Explicit for clarity; READ is the default
      originAccessLevels: [cloudfront.AccessLevel.READ],
    });

    // Create CloudFront distribution with S3 Origin Access Control (OAC)
    this.cloudfrontDistribution = new cloudfront.Distribution(this, 'Distribution', {
      defaultBehavior: {
        origin: s3Origin,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        functionAssociations: [
          {
            function: new cloudfront.Function(this, 'RootPathFunction', {
              code: cloudfront.FunctionCode.fromInline(`
                function handler(event) {
                  var request = event.request;
                  var uri = request.uri;
                  
                  // If accessing root path, serve index.html
                  if (uri === '/') {
                    request.uri = '/index.html';
                  }
                  
                  return request;
                }
              `),
            }),
            eventType: cloudfront.FunctionEventType.VIEWER_REQUEST,
          },
        ],
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
        new route53Targets.CloudFrontTarget(this.cloudfrontDistribution)
      ),
    });

    // Deploy webapp files to the same S3 bucket with cache invalidation
    new s3deploy.BucketDeployment(this, 'WebappDeployment', {
      sources: [s3deploy.Source.asset('../webapp')],
      destinationBucket: this.imageBucket,
      destinationKeyPrefix: '', // Upload to root of bucket
      distribution: this.cloudfrontDistribution,
      distributionPaths: ['/*'],
      prune: false, // Do not delete existing files in the bucket
    });



    // Create Lambda function for handling uploads
    const uploadFunction = new lambda.Function(this, 'UploadFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'upload_handler.handler',
      code: lambda.Code.fromAsset('../lambda'),
      timeout: cdk.Duration.minutes(1),
      memorySize: 256,
      environment: {
        BUCKET_NAME: this.imageBucket.bucketName,
      },
    });

    // Grant S3 write permissions to upload function
    this.imageBucket.grantWrite(uploadFunction);

    // Create Lambda layer for Pillow
    const pillowLayer = new lambda.LayerVersion(this, 'PillowLayer', {
      code: lambda.Code.fromAsset('../lambda/pillow-layer'),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'Pillow library for image processing',
    });

    // Create common utils layer (thumbnail_utils)
    const commonUtilsLayer = new lambda.LayerVersion(this, 'CommonUtilsLayer', {
      code: lambda.Code.fromAsset('../lambda/common-layer'),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'Common utilities (thumbnail_utils) for image functions',
    });

    // Create numpy layer for median image creation
    const numpyLayer = new lambda.LayerVersion(this, 'NumpyLayer', {
      code: lambda.Code.fromAsset('../lambda/numpy-layer'),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'NumPy library for numerical computations',
    });

    // Create Lambda function for image processing
    const imageProcessorFunction = new lambda.Function(this, 'ImageProcessorFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'image_processor.handler',
      code: lambda.Code.fromAsset('../lambda'),
      timeout: cdk.Duration.minutes(2),
      memorySize: 512,
      layers: [pillowLayer, commonUtilsLayer],
      environment: {
        BUCKET_NAME: this.imageBucket.bucketName,
      },
    });

    // Grant S3 read/write permissions to image processor function
    this.imageBucket.grantReadWrite(imageProcessorFunction);

    // Add S3 event notification to trigger image processor when uploads/latest.jpg is updated
    this.imageBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED_PUT,
      new s3n.LambdaDestination(imageProcessorFunction),
      { prefix: 'uploads/latest.jpg' }
    );

    // Create Lambda function for thumbnail synchronization
    const thumbnailSyncFunction = new lambda.Function(this, 'ThumbnailSyncFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'thumbnail_sync.handler',
      code: lambda.Code.fromAsset('../lambda'),
      timeout: cdk.Duration.minutes(5),
      memorySize: 512,
      layers: [pillowLayer, commonUtilsLayer],
      environment: {
        BUCKET_NAME: this.imageBucket.bucketName,
      },
    });

    // Grant S3 read/write permissions to thumbnail sync function
    this.imageBucket.grantReadWrite(thumbnailSyncFunction);

    // Create EventBridge rule to trigger thumbnail sync daily at 00:30 CET (23:30 UTC)
    const thumbnailSyncRule = new events.Rule(this, 'ThumbnailSyncRule', {
      schedule: events.Schedule.cron({
        minute: '30',
        hour: '23',
        day: '*',
        month: '*',
        year: '*',
      }),
      description: 'Trigger thumbnail sync daily at 00:30 CET',
    });

    // Add Lambda as target for the EventBridge rule
    thumbnailSyncRule.addTarget(new eventTargets.LambdaFunction(thumbnailSyncFunction));

    // Create API Gateway for upload endpoint
    const api = new apigateway.RestApi(this, 'UploadApi', {
      restApiName: `MailboxImageAnalyzer-${props.environment}`,
      description: 'API for uploading mailbox images',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
      },
      binaryMediaTypes: ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
    });

    // Create custom domain for API Gateway
    const apiDomain = new apigateway.DomainName(this, 'ApiDomain', {
      domainName: apiDomainName,
      certificate: certificate,
      securityPolicy: apigateway.SecurityPolicy.TLS_1_2,
    });

    // Create base path mapping for API Gateway
    new apigateway.BasePathMapping(this, 'ApiBasePathMapping', {
      domainName: apiDomain,
      restApi: api,
      basePath: '', // No base path, so API will be available at root
    });

    // Create DNS record for API subdomain pointing to API Gateway
    new route53.ARecord(this, 'ApiAliasRecord', {
      zone: hostedZone,
      recordName: props.environment === 'dev' ? 'api.mailbox-dev' : 'api.mailbox',
      target: route53.RecordTarget.fromAlias(
        new route53Targets.ApiGatewayDomain(apiDomain)
      ),
    });

    // Create API Gateway integration
    const uploadIntegration = new apigateway.LambdaIntegration(uploadFunction);

    // Add upload endpoint
    const uploadResource = api.root.addResource('upload');
    uploadResource.addMethod('POST', uploadIntegration);

    // Create Lambda function for listing images
    const listImagesFunction = new lambda.Function(this, 'ListImagesFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'list_images.handler',
      code: lambda.Code.fromAsset('../lambda'),
      timeout: cdk.Duration.minutes(1),
      memorySize: 256,
      environment: {
        BUCKET_NAME: this.imageBucket.bucketName,
      },
    });

    // Grant S3 read permissions to list images function
    this.imageBucket.grantRead(listImagesFunction);

    // Create Lambda function for getting statistics
    const getStatsFunction = new lambda.Function(this, 'GetStatsFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'get_stats.handler',
      code: lambda.Code.fromAsset('../lambda'),
      timeout: cdk.Duration.minutes(1),
      memorySize: 256,
      environment: {
        BUCKET_NAME: this.imageBucket.bucketName,
      },
    });

    // Grant S3 read permissions to get stats function
    this.imageBucket.grantRead(getStatsFunction);

    // Create Lambda function for moving images between folders
    const moveImagesFunction = new lambda.Function(this, 'MoveImagesFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'move_images.handler',
      code: lambda.Code.fromAsset('../lambda'),
      timeout: cdk.Duration.minutes(5),
      memorySize: 512,
      environment: {
        BUCKET_NAME: this.imageBucket.bucketName,
      },
    });

    // Grant S3 read/write permissions to move images function
    this.imageBucket.grantReadWrite(moveImagesFunction);

    // Create Lambda function for getting comparison status
    const getComparisonStatusFunction = new lambda.Function(this, 'GetComparisonStatusFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'get_comparison_status.handler',
      code: lambda.Code.fromAsset('../lambda'),
      timeout: cdk.Duration.minutes(1),
      memorySize: 256,
      environment: {
        BUCKET_NAME: this.imageBucket.bucketName,
      },
    });

    // Grant S3 read permissions to comparison status function
    this.imageBucket.grantRead(getComparisonStatusFunction);

    // Create Lambda function for median image creation
    const createMedianImageFunction = new lambda.Function(this, 'CreateMedianImageFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'create_median_image.handler',
      code: lambda.Code.fromAsset('../lambda'),
      timeout: cdk.Duration.minutes(10),
      memorySize: 1024,
      layers: [pillowLayer, numpyLayer],
      environment: {
        BUCKET_NAME: this.imageBucket.bucketName,
      },
    });

    // Grant S3 read/write permissions to median image creation function
    this.imageBucket.grantReadWrite(createMedianImageFunction);

    // Create EventBridge rule to trigger median image creation daily at 00:15 CET (23:15 UTC)
    const createMedianImageRule = new events.Rule(this, 'CreateMedianImageRule', {
      schedule: events.Schedule.cron({
        minute: '15',
        hour: '23',
        day: '*',
        month: '*',
        year: '*',
      }),
      description: 'Trigger median image creation daily at 00:15 CET',
    });

    // Add Lambda as target for the EventBridge rule
    createMedianImageRule.addTarget(new eventTargets.LambdaFunction(createMedianImageFunction));

    // Create Lambda function for comparing latest image with median
    const compareLatestWithMedianFunction = new lambda.Function(this, 'CompareLatestWithMedianFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'compare_latest_with_median.handler',
      code: lambda.Code.fromAsset('../lambda'),
      timeout: cdk.Duration.minutes(5),
      memorySize: 1024,
      layers: [pillowLayer, numpyLayer],
      environment: {
        BUCKET_NAME: this.imageBucket.bucketName,
      },
    });

    // Grant S3 read/write permissions to comparison function
    this.imageBucket.grantReadWrite(compareLatestWithMedianFunction);

    // Grant permission for image processor to invoke comparison function
    compareLatestWithMedianFunction.grantInvoke(imageProcessorFunction);

    // Add comparison function name to image processor environment
    imageProcessorFunction.addEnvironment('COMPARISON_FUNCTION_NAME', compareLatestWithMedianFunction.functionName);

    // Create Lambda function for editing statistics JSON
    const editStatisticsFunction = new lambda.Function(this, 'EditStatisticsFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'edit_statistics.handler',
      code: lambda.Code.fromAsset('../lambda'),
      timeout: cdk.Duration.minutes(1),
      memorySize: 256,
      environment: {
        BUCKET_NAME: this.imageBucket.bucketName,
      },
    });

    // Grant S3 read/write permissions to edit statistics function
    this.imageBucket.grantReadWrite(editStatisticsFunction);

    // Create API Gateway integrations
    const listImagesIntegration = new apigateway.LambdaIntegration(listImagesFunction);
    const getStatsIntegration = new apigateway.LambdaIntegration(getStatsFunction);
    const moveImagesIntegration = new apigateway.LambdaIntegration(moveImagesFunction);
    const getComparisonStatusIntegration = new apigateway.LambdaIntegration(getComparisonStatusFunction);
    const editStatisticsIntegration = new apigateway.LambdaIntegration(editStatisticsFunction);

    // Add list images endpoint
    const listImagesResource = api.root.addResource('list-images');
    listImagesResource.addMethod('GET', listImagesIntegration);

    // Add get stats endpoint
    const getStatsResource = api.root.addResource('stats');
    getStatsResource.addMethod('GET', getStatsIntegration);

    // Add move images endpoint
    const moveImagesResource = api.root.addResource('move-images');
    moveImagesResource.addMethod('POST', moveImagesIntegration);

    // Add comparison status endpoint
    const comparisonStatusResource = api.root.addResource('comparison-status');
    comparisonStatusResource.addMethod('GET', getComparisonStatusIntegration);

    // Add edit statistics endpoint
    const editStatisticsResource = api.root.addResource('edit-statistics');
    editStatisticsResource.addMethod('GET', editStatisticsIntegration);
    editStatisticsResource.addMethod('POST', editStatisticsIntegration);

    // Output the bucket ARN
    new cdk.CfnOutput(this, 'ImageBucketArn', {
      value: this.imageBucket.bucketArn,
      description: 'ARN of the S3 bucket for mailbox images',
      exportName: `MailboxImageBucketArn-${props.environment}`,
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

    // Output the API Gateway URL
    new cdk.CfnOutput(this, 'ApiGatewayUrl', {
      value: api.url,
      description: 'API Gateway URL for uploads',
      exportName: `ApiGatewayUrl-${props.environment}`,
    });

    // Output the custom API domain URL
    new cdk.CfnOutput(this, 'ApiCustomDomainUrl', {
      value: `https://${apiDomainName}`,
      description: 'Custom API domain URL for uploads',
      exportName: `ApiCustomDomainUrl-${props.environment}`,
    });
  }
}
