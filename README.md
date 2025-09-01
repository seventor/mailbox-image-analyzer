# Mailbox Image Analyzer

A CDK-based infrastructure for analyzing images captured by a camera inside a mailbox.

## Project Overview

This project creates AWS infrastructure for a mailbox image analyzer application with the following components:

- **S3 Bucket**: Secure storage for mailbox images with organized folder structure
- **Lambda Functions**: Serverless functions for image upload, processing, and thumbnail management
- **API Gateway**: REST API for image uploads, listing, and statistics with custom domain
- **CloudFront**: CDN for serving webapp and acting as S3 origin
- **Web Application**: Modern tabbed interface for viewing and browsing mailbox images

## How It Works

### Image Upload Process

1. **Upload API**: Images can be uploaded via POST request to `https://api.mailbox-dev.g103.net/upload`
2. **Storage**: Uploaded images are stored as `uploads/latest.jpg` in the S3 bucket
3. **Processing**: When `uploads/latest.jpg` is updated, a Lambda function is triggered
4. **Time Window**: Processing only occurs during specific time windows:
   - Last 5 minutes of each hour (minutes 55-59)
   - First 5 minutes of each hour (minutes 00-04)
5. **File Organization**: 
   - Original image copied to `usortert/YYYY-MM-DD-HH-MM.jpg`
   - Thumbnail created at `thumbnails/YYYY-MM-DD-HH-MM-thumbnail.jpg` (128px wide, maintaining aspect ratio)

### API Endpoints

- **POST /upload**: Accepts image uploads (Content-Type: image/jpeg)
  - Saves uploaded file as `uploads/latest.jpg` regardless of original filename
  - Returns success/error message with CORS headers
- **GET /list-images**: Lists images from specified folders with metadata
  - Query parameter: `folder` (usortert, ai-training-data/with-mail, ai-training-data/without-mail, uploads)
  - Returns image list with thumbnails, dates, and file information
- **GET /stats**: Provides image counts for each folder
  - Returns statistics for all monitored folders

### File Structure

```
S3 Bucket: mailbox-image-analyzer-dev
├── uploads/
│   └── latest.jpg                    # Latest uploaded image
├── usortert/
│   └── YYYY-MM-DD-HH-MM.jpg          # Timestamped copies
├── ai-training-data/
│   ├── with-mail/                     # Images classified as containing mail
│   └── without-mail/                  # Images classified as not containing mail
├── thumbnails/
│   └── YYYY-MM-DD-HH-MM-thumbnail.jpg # 256px wide thumbnails
└── index.html                         # Web application
```

## Infrastructure

### S3 Bucket

- **Name**: `mailbox-image-analyzer-{environment}`
- **Security**: All public access blocked, encryption enabled
- **Versioning**: Enabled for data protection
- **Lifecycle Rules**: Automatic cleanup of old images (1 year retention)
- **HTTPS Enforcement**: Denies non-HTTPS requests

### Lambda Functions

1. **Upload Function** (`upload_handler.py`):
   - Handles image uploads via API Gateway
   - Processes binary data from API Gateway
   - Saves images to S3 as `uploads/latest.jpg`

2. **Image Processor Function** (`image_processor.py`):
   - Triggered by S3 events when `uploads/latest.jpg` is updated
   - Only processes during specific time windows (minutes 55-59 or 00-04)
   - Copies images to `usortert` folder with timestamped filenames
   - Creates thumbnails (256px wide) in `thumbnails` folder
   - Uses shared Pillow library layer for image processing

3. **Thumbnail Sync Function** (`thumbnail_sync.py`):
   - Runs daily at 00:30 CET via EventBridge
   - Ensures all images in monitored folders have corresponding thumbnails
   - Creates missing thumbnails and removes orphaned ones
   - Maintains thumbnail consistency across all folders

4. **List Images Function** (`list_images.py`):
   - Provides API endpoint for listing images from specific folders
   - Returns image metadata including thumbnails, dates, and file information
   - Supports all monitored folders (usortert, with-mail, without-mail, uploads)

5. **Get Stats Function** (`get_stats.py`):
   - Provides API endpoint for folder statistics
   - Returns image counts for all monitored folders
   - Used by webapp for displaying tab labels with counts

### Lambda Layers

- **Pillow Layer**: Contains Pillow library for image processing
- **Common Utils Layer**: Contains shared utilities like `thumbnail_utils.py`
- **Shared Dependencies**: Ensures consistent code across Lambda functions

### API Gateway

- **Custom Domain**: `api.mailbox-dev.g103.net` (dev) / `api.mailbox.g103.net` (prod)
- **SSL Certificate**: Managed by AWS Certificate Manager
- **Binary Support**: Configured to handle image/jpeg, image/png, image/gif, image/webp
- **CORS**: Enabled for cross-origin requests

### CloudFront

- **Custom Domain**: `mailbox-dev.g103.net` (dev) / `mailbox.g103.net` (prod)
- **Origin**: S3 bucket with Origin Access Control (OAC)
- **Functions**: Root path (`/`) automatically serves `/index.html`
- **Error Handling**: 403/404 errors redirect to `/index.html`

## Web Application

The web application provides a modern, tabbed interface for viewing and browsing mailbox images. It's served via CloudFront and includes:

### Features
- **Tabbed Interface**: Overview, Usortert, With Mail, and Without Mail sections
- **Image Gallery**: Grid layout with thumbnails and metadata
- **Date Formatting**: Norwegian date format (DD.MM.YYYY HH:MM)
- **Responsive Design**: Works on mobile and desktop devices
- **Real-time Statistics**: Live image counts for each folder
- **Latest Upload Display**: Shows the most recent uploaded image

**Note**: The webapp is designed for viewing and browsing images only. Image uploads are handled via the API endpoint, not through the web interface.

### Local Development
A local development server script is included for testing:
```bash
./start-local-server.sh
```
This starts a local server at `http://localhost:8000/index.html` for development and testing.

## Prerequisites

Before deploying this infrastructure, ensure you have:

1. **AWS CLI** installed and configured
2. **Node.js** (version 16 or higher)
3. **AWS CDK** installed globally: `npm install -g aws-cdk`
4. **AWS credentials** configured for your target account
5. **Route 53 hosted zone** for `g103.net` domain

## Setup

1. **Install dependencies**:
   ```bash
   cd cdk && npm install
   ```

2. **Build the project**:
   ```bash
   npm run build
   ```

3. **Bootstrap CDK** (first time only):
   ```bash
   cdk bootstrap
   ```

## Deployment

### Development Environment

```bash
cd cdk && npm run deploy:dev
```

### Production Environment

```bash
cd cdk && npm run deploy:prod
```

### Using CDK Commands Directly

```bash
cd cdk && cdk deploy --context environment=dev
```

## Testing

### Upload an Image

```bash
curl -X POST -H "Content-Type: image/jpeg" \
  --data-binary @path/to/your/image.jpg \
  https://api.mailbox-dev.g103.net/upload
```

### Check Processing Results

```bash
# List files in usortert folder
aws s3 ls s3://mailbox-image-analyzer-dev/usortert/

# List thumbnails
aws s3 ls s3://mailbox-image-analyzer-dev/thumbnails/
```

## Environment Differences

| Feature | Development | Production |
|---------|-------------|------------|
| Bucket Name | `mailbox-image-analyzer-dev` | `mailbox-image-analyzer-prod` |
| Domain | `mailbox-dev.g103.net` | `mailbox.g103.net` |
| API Domain | `api.mailbox-dev.g103.net` | `api.mailbox.g103.net` |
| Removal Policy | Destroy | Retain |

## Project Structure

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
├── lambda/                       # Lambda functions
│   ├── upload_handler.py         # Image upload handler
│   ├── image_processor.py        # Image processing handler
│   ├── thumbnail_sync.py         # Daily thumbnail synchronization
│   ├── list_images.py            # API for listing images
│   ├── get_stats.py              # API for folder statistics
│   └── common-layer/             # Shared utilities layer
│       └── python/
│           └── thumbnail_utils.py # Thumbnail creation utilities
├── webapp/                       # Web application files
│   └── index.html                # Main webapp page
├── test-data/                    # Test images
│   └── with-mail/
├── start-local-server.sh         # Local development server script
├── package.json                  # Root project configuration
├── README.md                     # This file
└── instructions.md               # Project requirements
```

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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test the deployment
5. Submit a pull request

## License

This project is licensed under the MIT License.
