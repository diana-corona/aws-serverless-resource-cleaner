import boto3
import json
from datetime import datetime, timezone
from botocore.exceptions import ClientError

class OrphanResourceDiscovery:
    def __init__(self):
        self.cloudformation = boto3.client('cloudformation')
        self.lambda_client = boto3.client('lambda')
        self.s3 = boto3.client('s3')
        self.apigateway = boto3.client('apigateway')
        self.dynamodb = boto3.client('dynamodb')
        self.findings = {
            'stacks': [],
            'lambdas': [],
            's3_buckets': [],
            'api_gateways': [],
            'dynamodb_tables': []
        }

    def discover_stacks(self):
        """Discover CloudFormation stacks with Serverless pattern."""
        try:
            paginator = self.cloudformation.get_paginator('list_stacks')
            for page in paginator.paginate():
                for stack in page['StackSummaries']:
                    # Focus on active stacks (not already deleted)
                    if stack['StackStatus'] not in ['DELETE_COMPLETE']:
                        if 'serverless' in stack['StackName'].lower():
                            stack_detail = self.cloudformation.describe_stacks(
                                StackName=stack['StackName']
                            )['Stacks'][0]
                            
                            # Add stack details to findings
                            self.findings['stacks'].append({
                                'name': stack['StackName'],
                                'creation_time': stack['CreationTime'].isoformat(),
                                'status': stack['StackStatus'],
                                'last_updated': stack.get('LastUpdatedTime', '').isoformat() if 'LastUpdatedTime' in stack else None,
                                'description': stack_detail.get('Description', ''),
                                'tags': stack_detail.get('Tags', [])
                            })
        except ClientError as e:
            print(f"Error discovering stacks: {e}")

    def discover_lambdas(self):
        """Discover Lambda functions."""
        try:
            paginator = self.lambda_client.get_paginator('list_functions')
            for page in paginator.paginate():
                for function in page['Functions']:
                    # Check if function seems orphaned (no recent invocations, old creation date, etc)
                    self.findings['lambdas'].append({
                        'name': function['FunctionName'],
                        'runtime': function['Runtime'],
                        'creation_time': function['LastModified'],
                        'description': function.get('Description', ''),
                        'memory': function['MemorySize'],
                        'timeout': function['Timeout']
                    })
        except ClientError as e:
            print(f"Error discovering Lambda functions: {e}")

    def discover_s3_buckets(self):
        """Discover S3 buckets."""
        try:
            response = self.s3.list_buckets()
            for bucket in response['Buckets']:
                if 'serverless' in bucket['Name'].lower():
                    self.findings['s3_buckets'].append({
                        'name': bucket['Name'],
                        'creation_time': bucket['CreationDate'].isoformat()
                    })
        except ClientError as e:
            print(f"Error discovering S3 buckets: {e}")

    def discover_api_gateways(self):
        """Discover API Gateway APIs."""
        try:
            response = self.apigateway.get_rest_apis()
            for api in response['items']:
                if 'serverless' in api['name'].lower():
                    self.findings['api_gateways'].append({
                        'id': api['id'],
                        'name': api['name'],
                        'creation_time': api['createdDate'].isoformat(),
                        'description': api.get('description', '')
                    })
        except ClientError as e:
            print(f"Error discovering API Gateways: {e}")

    def discover_dynamodb_tables(self):
        """Discover DynamoDB tables."""
        try:
            paginator = self.dynamodb.get_paginator('list_tables')
            for page in paginator.paginate():
                for table_name in page['TableNames']:
                    if 'serverless' in table_name.lower():
                        table = self.dynamodb.describe_table(TableName=table_name)['Table']
                        self.findings['dynamodb_tables'].append({
                            'name': table_name,
                            'creation_time': table['CreationDateTime'].isoformat(),
                            'status': table['TableStatus'],
                            'size_bytes': table.get('TableSizeBytes', 0),
                            'item_count': table.get('ItemCount', 0)
                        })
        except ClientError as e:
            print(f"Error discovering DynamoDB tables: {e}")

    def run_discovery(self):
        """Run all discovery methods and generate report."""
        print("Starting resource discovery...")
        self.discover_stacks()
        self.discover_lambdas()
        self.discover_s3_buckets()
        self.discover_api_gateways()
        self.discover_dynamodb_tables()
        
        # Generate report
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        report_filename = f'orphan_resources_report_{timestamp}.json'
        
        with open(report_filename, 'w') as f:
            json.dump(self.findings, f, indent=2)
        
        print(f"\nDiscovery complete! Report saved to: {report_filename}")
        self.print_summary()

    def print_summary(self):
        """Print a summary of discovered resources."""
        print("\nResource Discovery Summary:")
        print("-" * 40)
        print(f"CloudFormation Stacks: {len(self.findings['stacks'])}")
        print(f"Lambda Functions: {len(self.findings['lambdas'])}")
        print(f"S3 Buckets: {len(self.findings['s3_buckets'])}")
        print(f"API Gateways: {len(self.findings['api_gateways'])}")
        print(f"DynamoDB Tables: {len(self.findings['dynamodb_tables'])}")

if __name__ == "__main__":
    discovery = OrphanResourceDiscovery()
    discovery.run_discovery()
