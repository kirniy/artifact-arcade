#!/bin/bash
# Setup Selectel S3 credentials for ARTIFACT arcade
#
# This script configures AWS CLI with Selectel S3 credentials.
# Run this on the Raspberry Pi as the kirniy user.
#
# Prerequisites:
# - AWS CLI installed: sudo apt install awscli
# - Selectel credentials from: https://my.selectel.ru/storage/containers
#
# Usage:
#   ./setup-aws-s3.sh
#   # Then enter your Selectel access key and secret key when prompted
#

set -e

echo "=== Selectel S3 Setup for ARTIFACT ==="
echo ""
echo "This will configure AWS CLI to use Selectel Object Storage."
echo "You need your Selectel S3 credentials from the dashboard."
echo ""

# Check if aws cli is installed
if ! command -v aws &> /dev/null; then
    echo "AWS CLI not found. Installing..."
    sudo apt update && sudo apt install -y awscli
fi

# Create AWS directory
mkdir -p ~/.aws

# Prompt for credentials
echo "Enter your Selectel Access Key ID:"
read -r AWS_ACCESS_KEY_ID

echo "Enter your Selectel Secret Access Key:"
read -rs AWS_SECRET_ACCESS_KEY
echo ""

# Write config file
cat > ~/.aws/config << EOF
[profile selectel]
region = ru-7
output = json
s3 =
    signature_version = s3v4
    addressing_style = path
EOF

# Write credentials file
cat > ~/.aws/credentials << EOF
[selectel]
aws_access_key_id = ${AWS_ACCESS_KEY_ID}
aws_secret_access_key = ${AWS_SECRET_ACCESS_KEY}
EOF

# Secure permissions
chmod 600 ~/.aws/credentials
chmod 600 ~/.aws/config

echo ""
echo "Configuration saved to ~/.aws/"
echo ""

# Test the connection
echo "Testing connection to Selectel S3..."
if aws --endpoint-url https://s3.ru-7.storage.selcloud.ru --profile selectel s3 ls s3://vnvnc 2>/dev/null; then
    echo ""
    echo "✅ Successfully connected to Selectel S3!"
    echo ""
    echo "ARTIFACT can now upload files. Restart the service:"
    echo "  sudo systemctl restart artifact"
else
    echo ""
    echo "❌ Failed to connect. Check your credentials."
    echo ""
    echo "You can get credentials from:"
    echo "  https://my.selectel.ru/storage/containers"
    echo ""
    echo "Delete and retry:"
    echo "  rm ~/.aws/credentials ~/.aws/config"
    echo "  ./setup-aws-s3.sh"
fi
