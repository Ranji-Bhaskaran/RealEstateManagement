import boto3
from django.conf import settings
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
import logging
from datetime import datetime
from django.contrib.auth.models import User

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
notifications_table = dynamodb.Table('Notifications')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_user_notifications(user_id):
    """
    Fetch unread notifications for a specific user from DynamoDB.
    """
    try:
        response = notifications_table.query(
            KeyConditionExpression=Key('user_id').eq(user_id),
            FilterExpression=Attr('is_read').eq(False)
        )
        notifications = response.get('Items', [])
        
        # Log the number of notifications found
        print(f"Fetched {len(notifications)} unread notifications for user {user_id}.")
        return notifications

    except Exception as e:
        logger.error("Error fetching notifications for user %s: %s", user_id, str(e))
        return []


def mark_notifications_as_read(user_id):
    """
    Marks all unread notifications for a specific user as read.
    """
    try:
        # Scan for unread notifications
        response = notifications_table.scan(
            FilterExpression=Attr('user_id').eq(user_id) & Attr('is_read').eq(False)
        )
        
        for notification in response.get('Items', []):
            # Update each notification's `is_read` attribute to True
            notifications_table.update_item(
                Key={
                    'user_id': user_id,
                    'notification_id': notification['notification_id']
                },
                UpdateExpression="SET is_read = :val",
                ExpressionAttributeValues={':val': True}
            )
        print(f"Marked notifications read for user {user_id}.")
    except Exception as e:
        logger.error("Error marking notifications as read for user %s: %s", user_id, str(e))

