# AWS Orphaned Resource Cleaner

A Python-based solution to help identify and clean up orphaned AWS resources, with a focus on Serverless framework deployments.

## Features

- Discovers potentially orphaned AWS resources across multiple services:
  - CloudFormation stacks
  - Lambda functions
  - S3 buckets
  - API Gateway APIs
  - DynamoDB tables
- Generates detailed reports of found resources
- Provides safe, controlled cleanup process
- Supports both Serverless framework and direct AWS resource removal

## Prerequisites

- Python 3.6+
- AWS credentials configured
- Serverless Framework (if using Serverless deployments)

## Installation

1. Clone this repository

2. Create and activate a virtual environment:
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
.\venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure AWS credentials using one of these methods:
   - AWS CLI: Run `aws configure`
   - Environment variables:
     ```bash
     export AWS_ACCESS_KEY_ID='your_access_key'
     export AWS_SECRET_ACCESS_KEY='your_secret_key'
     export AWS_DEFAULT_REGION='your_region'
     ```

## Usage

### 1. Discover Orphaned Resources

Run the discovery script to scan your AWS account for potentially orphaned resources:

```bash
python discover_orphans.py
```

This will:
- Scan your AWS account for resources
- Generate a JSON report file (e.g., `orphan_resources_report_20250729_231259.json`)
- Display a summary of found resources

### 2. Review the Report

The generated report contains detailed information about potentially orphaned resources. Review this carefully to identify which resources should be removed.

### 3. Clean Up Resources

Use the cleanup script to remove specific resources:

```bash
python cleanup_resources.py <report_file> <resource_id1> <resource_id2> ...
```

Example:
```bash
python cleanup_resources.py orphan_resources_report_20250729_231259.json my-stack-name my-lambda-function
```

## Safety Features

- Discovery is read-only and never modifies resources
- Cleanup requires explicit resource IDs
- Stack removal tries Serverless framework first, then falls back to CloudFormation
- S3 buckets are emptied before deletion
- Detailed error reporting for each cleanup operation
- Resources are processed one at a time

## Resource Types

The tool handles these AWS resource types:

| Resource Type | Detection Method | Cleanup Method |
|--------------|------------------|----------------|
| CloudFormation Stacks | Name contains 'serverless' | Serverless remove or CloudFormation delete |
| Lambda Functions | All functions in account | Direct deletion |
| S3 Buckets | Name contains 'serverless' | Empty and delete |
| API Gateway APIs | Name contains 'serverless' | Direct deletion |
| DynamoDB Tables | Name contains 'serverless' | Direct deletion |

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## License

MIT

## Safety Warning

⚠️ Always review the discovery report carefully before deleting any resources. Resource deletion is irreversible!
