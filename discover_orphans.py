import boto3
import json
import logging
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OrphanResourceDiscovery:
    # Default thresholds
    DEFAULT_AGE_THRESHOLD_DAYS = 90  # Resources older than 90 days
    DEFAULT_LAMBDA_INVOCATION_THRESHOLD = 0  # No invocations in monitoring period
    DEFAULT_MONITORING_PERIOD_DAYS = 30  # Check metrics for last 30 days
    def __init__(self, age_threshold_days=None, lambda_invocation_threshold=None, monitoring_period_days=None):
        # Common AWS regions
        self.regions = [
            'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'eu-west-1', 'eu-west-2', 'eu-west-3',
            'eu-central-1', 'eu-north-1',
            'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3',
            'ap-southeast-1', 'ap-southeast-2',
            'ap-south-1',
            'sa-east-1',
            'ca-central-1'
        ]
        self.s3 = boto3.client('s3')  # S3 is global, no need for regional clients
        
        # Initialize regional clients as dictionaries
        self.cloudformation = {}
        self.lambda_client = {}
        self.cloudwatch = {}
        self.apigateway = {}
        self.dynamodb = {}
        
        # Create clients for each region
        for region in self.regions:
            self.cloudformation[region] = boto3.client('cloudformation', region_name=region)
            self.lambda_client[region] = boto3.client('lambda', region_name=region)
            self.cloudwatch[region] = boto3.client('cloudwatch', region_name=region)
            self.apigateway[region] = boto3.client('apigateway', region_name=region)
            self.dynamodb[region] = boto3.client('dynamodb', region_name=region)
        
        # Set thresholds
        self.age_threshold_days = age_threshold_days or self.DEFAULT_AGE_THRESHOLD_DAYS
        self.lambda_invocation_threshold = lambda_invocation_threshold or self.DEFAULT_LAMBDA_INVOCATION_THRESHOLD
        self.monitoring_period_days = monitoring_period_days or self.DEFAULT_MONITORING_PERIOD_DAYS
        
        # Calculate age threshold date
        self.age_threshold_date = datetime.now(timezone.utc) - timedelta(days=self.age_threshold_days)
        self.monitoring_start_date = datetime.now(timezone.utc) - timedelta(days=self.monitoring_period_days)
        self.findings = {
            'stacks': [],
            'lambdas': [],
            's3_buckets': [],
            'api_gateways': [],
            'dynamodb_tables': []
        }

    def is_resource_old(self, creation_time):
        """Check if a resource is older than the age threshold."""
        if isinstance(creation_time, str):
            creation_time = datetime.fromisoformat(creation_time.replace('Z', '+00:00'))
        return creation_time < self.age_threshold_date

    def get_lambda_metrics(self, function_name, region):
        """Get Lambda function metrics from CloudWatch."""
        try:
            response = self.cloudwatch[region].get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Invocations',
                Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                StartTime=self.monitoring_start_date,
                EndTime=datetime.now(timezone.utc),
                Period=self.monitoring_period_days * 24 * 60 * 60,  # Period in seconds
                Statistics=['Sum']
            )
            
            # Sum all invocations in the period
            total_invocations = sum(datapoint['Sum'] for datapoint in response['Datapoints'])
            return total_invocations
        except ClientError as e:
            logger.error(f"Error getting metrics for Lambda {function_name}: {e}")
            return None

    def discover_stacks(self):
        """Discover potentially orphaned CloudFormation stacks with Serverless pattern."""
        for region in self.regions:
            try:
                logger.info(f"Searching stacks in region {region}")
                paginator = self.cloudformation[region].get_paginator('list_stacks')
                for page in paginator.paginate():
                    for stack in page['StackSummaries']:
                        # Focus on active stacks (not already deleted)
                        if stack['StackStatus'] not in ['DELETE_COMPLETE']:
                            if ('serverless' in stack['StackName'].lower() and 
                                self.is_resource_old(stack['CreationTime'])):
                                stack_detail = self.cloudformation[region].describe_stacks(
                                    StackName=stack['StackName']
                                )['Stacks'][0]
                                
                                # Add potentially orphaned stack to findings
                                self.findings['stacks'].append({
                                    'name': stack['StackName'],
                                    'creation_time': stack['CreationTime'].isoformat(),
                                    'status': stack['StackStatus'],
                                    'last_updated': stack.get('LastUpdatedTime', '').isoformat() if 'LastUpdatedTime' in stack else None,
                                    'description': stack_detail.get('Description', ''),
                                    'tags': stack_detail.get('Tags', [])
                                })
            except ClientError as e:
                print(f"Error discovering stacks in {region}: {e}")

    def discover_lambdas(self):
        """Discover potentially orphaned Lambda functions based on age and invocation metrics."""
        for region in self.regions:
            try:
                logger.info(f"Searching Lambda functions in region {region}")
                paginator = self.lambda_client[region].get_paginator('list_functions')
                for page in paginator.paginate():
                    for function in page['Functions']:
                        # Parse the last modified time
                        last_modified = datetime.strptime(
                            function['LastModified'].split('.')[0],
                            '%Y-%m-%dT%H:%M:%S'
                        ).replace(tzinfo=timezone.utc)
                        
                        # Check if function is old and has no recent invocations
                        if self.is_resource_old(last_modified):
                            invocations = self.get_lambda_metrics(function['FunctionName'], region)
                            if invocations is not None and invocations <= self.lambda_invocation_threshold:
                                self.findings['lambdas'].append({
                                    'name': function['FunctionName'],
                                    'runtime': function['Runtime'],
                                    'creation_time': function['LastModified'],
                                    'description': function.get('Description', ''),
                                    'memory': function['MemorySize'],
                                    'timeout': function['Timeout']
                                })
            except ClientError as e:
                print(f"Error discovering Lambda functions in {region}: {e}")

    def discover_s3_buckets(self):
        """Discover S3 buckets."""
        try:
            response = self.s3.list_buckets()
            for bucket in response['Buckets']:
                if ('serverless' in bucket['Name'].lower() and 
                    self.is_resource_old(bucket['CreationDate'])):
                    self.findings['s3_buckets'].append({
                        'name': bucket['Name'],
                        'creation_time': bucket['CreationDate'].isoformat()
                    })
        except ClientError as e:
            print(f"Error discovering S3 buckets: {e}")

    def discover_api_gateways(self):
        """Discover API Gateway APIs."""
        for region in self.regions:
            try:
                logger.info(f"Searching API Gateways in region {region}")
                response = self.apigateway[region].get_rest_apis()
                for api in response['items']:
                    if ('serverless' in api['name'].lower() and 
                        self.is_resource_old(api['createdDate'])):
                        self.findings['api_gateways'].append({
                            'id': api['id'],
                            'name': api['name'],
                            'creation_time': api['createdDate'].isoformat(),
                            'description': api.get('description', '')
                        })
            except ClientError as e:
                print(f"Error discovering API Gateways in {region}: {e}")

    def discover_dynamodb_tables(self):
        """Discover DynamoDB tables."""
        for region in self.regions:
            try:
                logger.info(f"Searching DynamoDB tables in region {region}")
                paginator = self.dynamodb[region].get_paginator('list_tables')
                for page in paginator.paginate():
                    for table_name in page['TableNames']:
                        if 'serverless' in table_name.lower():
                            table = self.dynamodb[region].describe_table(TableName=table_name)['Table']
                            if self.is_resource_old(table['CreationDateTime']):
                                self.findings['dynamodb_tables'].append({
                                    'name': table_name,
                                    'creation_time': table['CreationDateTime'].isoformat(),
                                    'status': table['TableStatus'],
                                    'size_bytes': table.get('TableSizeBytes', 0),
                                    'item_count': table.get('ItemCount', 0)
                                })
            except ClientError as e:
                print(f"Error discovering DynamoDB tables in {region}: {e}")

    def run_discovery(self):
        """Run all discovery methods and generate report."""
        logger.info("Starting resource discovery...")
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
        
        logger.info(f"Discovery complete! Report saved to: {report_filename}")
        self.print_summary()

    def print_summary(self):
        """Print a summary of discovered resources."""
        logger.info("\nResource Discovery Summary:")
        logger.info("-" * 40)
        logger.info(f"CloudFormation Stacks: {len(self.findings['stacks'])}")
        logger.info(f"Lambda Functions: {len(self.findings['lambdas'])}")
        logger.info(f"S3 Buckets: {len(self.findings['s3_buckets'])}")
        logger.info(f"API Gateways: {len(self.findings['api_gateways'])}")
        logger.info(f"DynamoDB Tables: {len(self.findings['dynamodb_tables'])}")
        
        # Log threshold settings used
        logger.info("\nThresholds Used:")
        logger.info(f"Age Threshold: {self.age_threshold_days} days")
        logger.info(f"Lambda Invocation Threshold: {self.lambda_invocation_threshold} invocations")
        logger.info(f"Monitoring Period: {self.monitoring_period_days} days")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Discover potentially orphaned AWS serverless resources.')
    parser.add_argument('--age-threshold', type=int, help='Age threshold in days', default=None)
    parser.add_argument('--lambda-threshold', type=int, help='Lambda invocation threshold', default=None)
    parser.add_argument('--monitoring-period', type=int, help='Monitoring period in days', default=None)
    
    args = parser.parse_args()
    
    discovery = OrphanResourceDiscovery(
        age_threshold_days=args.age_threshold,
        lambda_invocation_threshold=args.lambda_threshold,
        monitoring_period_days=args.monitoring_period
    )
    
    discovery.run_discovery()
