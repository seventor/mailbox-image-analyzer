#!/bin/bash

# Script to process each image in with-mail folder
# For each image: copy to latest.jpg, trigger comparison, wait, then move to next

BUCKET="mailbox-image-analyzer-dev"
API_BASE="https://api.mailbox-dev.g103.net"

echo "Starting to process images in with-mail folder..."

# Get list of images (excluding .keep file)
IMAGES=$(aws s3 ls s3://$BUCKET/ai-training-data/with-mail/ --recursive | grep "\.jpg$" | awk '{print $4}')

# Count total images
TOTAL=$(echo "$IMAGES" | wc -l)
echo "Found $TOTAL images to process"

COUNTER=1

# Process each image
echo "$IMAGES" | while read -r image_path; do
    if [ -n "$image_path" ]; then
        echo ""
        echo "=== Processing image $COUNTER/$TOTAL: $image_path ==="
        
        # Copy image to latest.jpg
        echo "Copying $image_path to uploads/latest.jpg..."
        aws s3 cp "s3://$BUCKET/$image_path" "s3://$BUCKET/uploads/latest.jpg"
        
        if [ $? -eq 0 ]; then
            echo "✓ Successfully copied to latest.jpg"
            
            # Wait a moment for S3 to be consistent
            echo "Waiting 2 seconds for S3 consistency..."
            sleep 2
            
            # Trigger comparison
            echo "Triggering comparison..."
            RESPONSE=$(curl -s -X POST "$API_BASE/trigger-comparison" -H "Content-Type: application/json")
            
            if echo "$RESPONSE" | grep -q "success.*true"; then
                echo "✓ Comparison triggered successfully"
                
                # Wait for comparison to complete (give it time to process)
                echo "Waiting 10 seconds for comparison to complete..."
                sleep 10
                
                # Check comparison status
                echo "Checking comparison status..."
                STATUS_RESPONSE=$(curl -s "$API_BASE/comparison-status")
                echo "Status: $STATUS_RESPONSE"
                
            else
                echo "✗ Failed to trigger comparison: $RESPONSE"
            fi
            
        else
            echo "✗ Failed to copy image to latest.jpg"
        fi
        
        COUNTER=$((COUNTER + 1))
        
        # Add a small delay between images
        if [ $COUNTER -le $TOTAL ]; then
            echo "Waiting 3 seconds before next image..."
            sleep 3
        fi
    fi
done

echo ""
echo "=== Processing complete! ==="
echo "Processed $TOTAL images from with-mail folder"
