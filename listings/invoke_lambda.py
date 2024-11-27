import boto3
import json

def invoke_lambda_function(lambda_name, payload):
    # Initialize a boto3 client for Lambda
    client = boto3.client('lambda')

    # Invoke the Lambda function
    response = client.invoke(
        FunctionName=lambda_name,
        InvocationType='RequestResponse',  # Use 'Event' for asynchronous execution
        Payload=json.dumps(payload),
    )

    # Read the response
    response_payload = response['Payload'].read()
    print("Response from Lambda:", response_payload.decode('utf-8'))

if __name__ == "__main__":
    lambda_function_name = 'MyLambdaFunction'  # Replace with your function name
    test_payload = {
        # Include test data that mimics the DynamoDB stream event
        "Records": [
            {
                "eventName": "MODIFY",
                "dynamodb": {
                    "NewImage": {
                        "id": {"S": "1"},
                        "price": {"N": "200.00"}
                    },
                    "OldImage": {
                        "id": {"S": "1"},
                        "price": {"N": "250.00"}
                    }
                }
            }
        ]
    }
    invoke_lambda_function(lambda_function_name, test_payload)
