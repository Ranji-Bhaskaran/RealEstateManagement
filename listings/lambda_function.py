import os
import django
import json
import boto3
import logging
from datetime import datetime
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
from django.conf import settings

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestate_project.settings')
logger.info("DJANGO_SETTINGS_MODULE set to: %s", os.environ['DJANGO_SETTINGS_MODULE'])
print("DJANGO_SETTINGS_MODULE set to:", os.environ['DJANGO_SETTINGS_MODULE'])

django.setup()
from django.contrib.auth.models import User
from listings.models import Property, Favorite

# Initialize DynamoDB resources
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
listings_table = dynamodb.Table('ListingTable')
notifications_table = dynamodb.Table('Notifications')

def lambda_handler(event, context):
    logger.info("Lambda function invoked with event: %s", json.dumps(event, indent=2))
    print("Received event:", event)

    records = event.get('Records', [])
    if not records:
        logger.warning("No 'Records' found in the event.")
        return {
            'statusCode': 400,
            'body': json.dumps('No records found in the event.')
        }

    for record in records:
        try:
            if record['eventName'] == 'MODIFY':
                new_image = record['dynamodb'].get('NewImage', {})
                old_image = record['dynamodb'].get('OldImage', {})

                logger.debug("NewImage: %s", json.dumps(new_image, indent=2))
                logger.debug("OldImage: %s", json.dumps(old_image, indent=2))

                property_id = new_image.get('id', {}).get('S')
                new_price_field = new_image.get('price', {})
                old_price_field = old_image.get('price', {})
                logger.info("New Price Field: %s", new_price_field)
                logger.info("Old Price Field: %s", old_price_field)
                new_price_str = new_price_field.get('S') or new_price_field.get('N')
                old_price_str = old_price_field.get('S') or old_price_field.get('N')

                if property_id is None:
                    logger.warning("Property ID is missing.")
                    continue
                if new_price_str is None:
                    logger.warning("New Price is missing or not accessible as 'S' or 'N'.")
                    continue
                if old_price_str is None:
                    logger.warning("Old Price is missing or not accessible as 'S' or 'N'.")
                    continue

                # Attempt conversion to float with try-except to catch any remaining issues
                try:
                    new_price = float(new_price_str)
                    old_price = float(old_price_str)
                except ValueError as e:
                    logger.error("ValueError converting price to float: %s", e)
                    continue

                logger.info("Property ID: %s | Old Price: %s | New Price: %s", property_id, old_price, new_price)

                if new_price < old_price:
                    logger.info("Price dropped for Property ID: %s. Notifying users.", property_id)
                    create_notifications_for_all_users(property_id, old_price, new_price)

        except ClientError as e:
            logger.error("ClientError: %s", e)
        except KeyError as e:
            logger.error("KeyError: %s in record: %s", e, record)
        except Exception as e:
            logger.error("Unexpected error: %s", e)

def create_notifications_for_all_users(property_id, old_price, new_price):
    """
    Retrieve all users and create notifications in DynamoDB for a property price drop.
    """
    message = f"The price of a property has dropped from ${old_price} to ${new_price}! Check it out!"

    # Fetch all user IDs
    all_users = User.objects.values_list('id', flat=True)
    logger.info("Fetched user IDs for notifications: %s", list(all_users))

    for user_id in all_users:
        logger.info(f"Creating notification for user {user_id}")  # Log each user ID before creating notification
        try:
            notification_id = get_next_notification_id(user_id)
            notifications_table.put_item(
                Item={
                    'user_id': str(user_id),
                    'notification_id': notification_id,
                    'property_id': str(property_id),
                    'message': message,
                    'is_read': False,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            logger.info(f"Notification created successfully for user {user_id}")

        except ClientError as e:
            logger.error(f"ClientError while creating notification for user {user_id}: {e.response['Error']['Message']}")
        except Exception as e:
            logger.error(f"Error creating notification for user {user_id}: {str(e)}")

    logger.info("Completed creating notifications for all users.")

def get_next_notification_id(user_id):
    """
    Retrieve the next notification ID for a user by finding the highest current ID and adding one.
    """
    try:
        response = notifications_table.query(
            KeyConditionExpression=Key('user_id').eq(str(user_id)),
            ProjectionExpression='notification_id'
        )
        items = response.get('Items', [])
        max_id = max(int(item['notification_id']) for item in items) if items else 0
        return str(max_id + 1)

    except ClientError as e:
        logger.error(f"ClientError while fetching notifications for user {user_id}: {e.response['Error']['Message']}")
        return "1"  # Default to '1' if query fails or no items found
    except Exception as e:
        logger.error(f"Error fetching notifications for user {user_id}: {str(e)}")
        return "1"
