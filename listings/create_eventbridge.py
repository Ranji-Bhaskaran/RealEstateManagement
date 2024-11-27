import boto3
import logging
import json

# Initialize logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Boto3 clients
lambda_client = boto3.client('lambda', region_name='us-east-1')
events_client = boto3.client('events', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

function_name = 'MyLambdaFunction'
rule_name = 'MyScheduledRule'
description = 'Rule to invoke MyScheduledFunction every 2 minutes'
table_name = 'Notifications'

try:
    rule_response = events_client.put_rule(
        Name=rule_name,
        ScheduleExpression='rate(2 minutes)',  # Trigger every 2 minutes
        State='ENABLED',
        Description=description
    )
    logger.info(f"EventBridge rule created: {rule_response['RuleArn']}")
except Exception as e:
    logger.error(f"Failed to create EventBridge rule: {e}")

try:
    target_response = events_client.put_targets(
        Rule=rule_name,
        Targets=[
            {
                'Id': '1',
                'Arn': f'arn:aws:lambda:us-east-1:533267406417:function:{function_name}',
                'Input': json.dumps({'action': 'price_drop_check'})
            }
        ]
    )
    logger.info("Lambda function added as target for EventBridge rule.")
except Exception as e:
    logger.error(f"Failed to add Lambda function as target: {e}")

try:
    lambda_client.add_permission(
        FunctionName=function_name,
        StatementId='MyScheduledRulePermission',
        Action='lambda:InvokeFunction',
        Principal='events.amazonaws.com',
        SourceArn=rule_response['RuleArn']
    )
    logger.info("Permission granted to EventBridge to invoke Lambda function.")
except Exception as e:
    logger.error(f"Failed to grant permission: {e}")

# Lambda handler function
def lambda_handler(event, context):
    logger.info("Lambda function triggered by EventBridge rule.")
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        property_id = event.get('property_id', 'unknown')
        new_price = event.get('new_price', 0)
        
        # Insert a notification in DynamoDB when price drops
        table = dynamodb.Table(table_name)
        notification = {
            'property_id': property_id,
            'message': f"Price dropped to ${new_price}!",
            'timestamp': int(context.timestamp),
        }
        table.put_item(Item=notification)
        
        logger.info(f"Notification added to DynamoDB for property ID {property_id}: {notification['message']}")
    except Exception as e:
        logger.error(f"Error while processing price drop notification: {e}")

    return {
        'statusCode': 200,
        'body': json.dumps('Lambda function executed successfully')
    }
