import boto3

# Initialize a Boto3 client for Lambda
lambda_client = boto3.client('lambda', region_name='us-east-1')

# Read the deployment package
with open('function.zip', 'rb') as f:
    zip_file = f.read()

# Create the Lambda function
response = lambda_client.create_function(
    FunctionName='MyLambdaFunction',
    Role='arn:aws:iam::533267406417:role/LabRole',
    Handler='lambda_function.lambda_handler', 
    Runtime='python3.9',
    Code={
        'ZipFile': zip_file
    },
    Description='A Lambda function to call in App notification',
    Timeout=15,
    MemorySize=128,
    Publish=True
)

print(response)