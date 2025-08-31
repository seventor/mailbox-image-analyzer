I want to create an app that analyses images taken from a camera inside a mailbox.
The app should consist of several parts:
- A simple webapp that shown the images taken
- Lamdbda functions that handles images stored in a S3

# Api
There should be an API that handles requests from the browser. The API should have the functionality listed below.

## Upload
An upload end-point that can take a POST request, and a client can upload a "latest.jpg" file. That file should be placed in the "uploads" folder in the root S3 bucket.

# Serverside functionality

# Upload
When the file "uploads/latest.jpg" is updated in the S3 bucket, a function should copy that image to the "usortert" folder in the root of the bucket. The file should have the filename YYYY-MM-DD-HH-MM.jpg based on when the file was copied to the new folder. If there is a file already with that name, then overwrite it. At the same time, make a thumbnail of the image, and store that thumbnail in the "thumbnails" folder in the root of the S3 bucket, using this naming convention: YYYY-MM-DD-HH-MM-thumbnail.jpg. The thumbnail should be 128px wide, but keep the aspect ratio from the original.

# General
- When I ask a question, do not just chnage code. Just answer the question, and then maybe ask if you should change files and code

# CDK and AWS
- All files realted to CDK ans AWS deployment should reside in the subdirectory named 'cdk'
- Do not run AWS CLI commands or CDK Deployments before asking

# Webapp
- All files that are part of the webapp should reside in the subdirectory 'webapp'.
- This subdirectory will contain all html, css, javascript and be uploaded to the S3 bucket.

# GIT
- Never commit anything before asking