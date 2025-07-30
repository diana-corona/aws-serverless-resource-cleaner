import boto3
import json
import argparse
import subprocess
from botocore.exceptions import ClientError

class ResourceCleaner:
    def __init__(self):
        self.cloudformation = boto3.client('cloudformation')
        self.lambda_client = boto3.client('lambda')
        self.s3 = boto3.client('s3')
        self.apigateway = boto3.client('apigateway')
        self.dynamodb = boto3.client('dynamodb')

    def delete_stack(self, stack_name):
        """Delete a CloudFormation stack."""
        try:
            print(f"Attempting to delete stack: {stack_name}")
            # Try serverless removal first
            try:
                result = subprocess.run(['serverless', 'remove', '--stack', stack_name], 
                                     capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"Successfully removed stack {stack_name} using serverless framework")
                    return True
            except Exception as e:
                print(f"Failed to remove using serverless framework, falling back to CloudFormation: {e}")

            # Fallback to CloudFormation deletion
            self.cloudformation.delete_stack(StackName=stack_name)
            print(f"Stack deletion initiated for {stack_name}")
            return True
        except ClientError as e:
            print(f"Error deleting stack {stack_name}: {e}")
            return False

    def empty_and_delete_bucket(self, bucket_name):
        """Empty and delete an S3 bucket."""
        try:
            print(f"Emptying bucket: {bucket_name}")
            bucket = boto3.resource('s3').Bucket(bucket_name)
            bucket.objects.all().delete()
            bucket.object_versions.all().delete()
            
            print(f"Deleting bucket: {bucket_name}")
            self.s3.delete_bucket(Bucket=bucket_name)
            return True
        except ClientError as e:
            print(f"Error deleting bucket {bucket_name}: {e}")
            return False

    def delete_lambda_function(self, function_name):
        """Delete a Lambda function."""
        try:
            print(f"Deleting Lambda function: {function_name}")
            self.lambda_client.delete_function(FunctionName=function_name)
            return True
        except ClientError as e:
            print(f"Error deleting Lambda function {function_name}: {e}")
            return False

    def delete_api_gateway(self, api_id):
        """Delete an API Gateway."""
        try:
            print(f"Deleting API Gateway: {api_id}")
            self.apigateway.delete_rest_api(restApiId=api_id)
            return True
        except ClientError as e:
            print(f"Error deleting API Gateway {api_id}: {e}")
            return False

    def delete_dynamodb_table(self, table_name):
        """Delete a DynamoDB table."""
        try:
            print(f"Deleting DynamoDB table: {table_name}")
            self.dynamodb.delete_table(TableName=table_name)
            return True
        except ClientError as e:
            print(f"Error deleting DynamoDB table {table_name}: {e}")
            return False

    def cleanup_resources(self, report_file, resource_ids):
        """Clean up specified resources from the report."""
        try:
            with open(report_file, 'r') as f:
                report = json.load(f)
        except FileNotFoundError:
            print(f"Report file not found: {report_file}")
            return

        results = {
            'successful': [],
            'failed': []
        }

        for resource_id in resource_ids:
            # Handle stacks
            for stack in report['stacks']:
                if stack['name'] == resource_id:
                    if self.delete_stack(resource_id):
                        results['successful'].append(('stack', resource_id))
                    else:
                        results['failed'].append(('stack', resource_id))

            # Handle S3 buckets
            for bucket in report['s3_buckets']:
                if bucket['name'] == resource_id:
                    if self.empty_and_delete_bucket(resource_id):
                        results['successful'].append(('s3_bucket', resource_id))
                    else:
                        results['failed'].append(('s3_bucket', resource_id))

            # Handle Lambda functions
            for func in report['lambdas']:
                if func['name'] == resource_id:
                    if self.delete_lambda_function(resource_id):
                        results['successful'].append(('lambda', resource_id))
                    else:
                        results['failed'].append(('lambda', resource_id))

            # Handle API Gateways
            for api in report['api_gateways']:
                if api['id'] == resource_id:
                    if self.delete_api_gateway(resource_id):
                        results['successful'].append(('api_gateway', resource_id))
                    else:
                        results['failed'].append(('api_gateway', resource_id))

            # Handle DynamoDB tables
            for table in report['dynamodb_tables']:
                if table['name'] == resource_id:
                    if self.delete_dynamodb_table(resource_id):
                        results['successful'].append(('dynamodb', resource_id))
                    else:
                        results['failed'].append(('dynamodb', resource_id))

        # Print results
        print("\nCleanup Results:")
        print("-" * 40)
        print("\nSuccessfully deleted:")
        for resource_type, resource_id in results['successful']:
            print(f"- {resource_type}: {resource_id}")
        
        print("\nFailed to delete:")
        for resource_type, resource_id in results['failed']:
            print(f"- {resource_type}: {resource_id}")

def main():
    parser = argparse.ArgumentParser(description='Clean up AWS resources based on discovery report')
    parser.add_argument('report_file', help='Path to the resource discovery report JSON file')
    parser.add_argument('resource_ids', nargs='+', help='IDs of resources to clean up')
    
    args = parser.parse_args()
    
    cleaner = ResourceCleaner()
    cleaner.cleanup_resources(args.report_file, args.resource_ids)

if __name__ == "__main__":
    main()
