import boto3
import logging
from botocore.exceptions import ClientError
from decimal import Decimal

# Initialize the S3, DynamoDB, and SNS clients
s3 = boto3.client('s3', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
sns_client = boto3.client('sns', region_name='us-east-1')
bucket_name = 'realestate-listing-images'
dynamodb_table_name = 'ListingTable'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# S3 Section
def create_s3_bucket(bucket_name):
    """Create an S3 bucket if it doesn't exist."""
    try:
        s3.create_bucket(Bucket=bucket_name)
        logging.info(f"Bucket '{bucket_name}' created successfully.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
            logging.info(f"Bucket '{bucket_name}' already exists and is owned by you.")
        else:
            logging.error(f"Failed to create bucket: {e.response['Error']['Message']}")

def upload_to_s3(file, filename, bucket_name):
    """Uploads a file to the specified S3 bucket and sets it to public-read."""
    try:
        # Upload the file to S3
        s3.upload_fileobj(file, bucket_name, filename)
        logging.info(f"File '{filename}' uploaded to bucket '{bucket_name}'.")

        # Set the ACL to public-read
        s3.put_object_acl(Bucket=bucket_name, Key=filename, ACL='public-read')
        logging.info(f"ACL set to public-read for '{filename}' in bucket '{bucket_name}'.")

        # Construct the public URL for the uploaded file
        image_url = f'https://{bucket_name}.s3.amazonaws.com/{filename}'
        return image_url

    except ClientError as e:
        logging.error(f"Failed to upload file: {e.response['Error']['Message']}")
        return None
        
def delete_item_from_s3(bucket_name, key):
    """Deletes an item from the specified S3 bucket.

    Args:
        bucket_name (str): The name of the S3 bucket.
        key (str): The key (file path) of the item to delete.

    Returns:
        bool: True if the item was deleted successfully, False otherwise.
    """
    s3_client = boto3.client('s3', region_name='us-east-1')

    try:
        # Attempt to delete the object from the S3 bucket
        s3_client.delete_object(Bucket=bucket_name, Key=key)
        print(f"Successfully deleted {key} from S3 bucket {bucket_name}.")
        return True
        
    except s3_client.exceptions.NoSuchKey:
        print(f"The key {key} does not exist in bucket {bucket_name}.")
        return False
    except Exception as e:
        print(f"Error deleting {key} from S3 bucket {bucket_name}: {e}")
        return False


# DynamoDB Section
def create_dynamodb_table(table_name='ListingTable'):
    """Creates a DynamoDB table if it does not already exist."""
    existing_tables = dynamodb.tables.all()
    if any(table.name == table_name for table in existing_tables):
        print(f"Table '{table_name}' already exists.")
        return

    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'id',
                    'KeyType': 'HASH'  # Partition key
                },
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'id',
                    'AttributeType': 'S'  # String
                },
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        table.wait_until_exists()  # Wait until the table is created
        print(f"Table '{table_name}' created successfully.")
    except ClientError as e:
        print(f"Failed to create table: {e.response['Error']['Message']}")

def insert_item_to_dynamodb(item, table_name='ListingTable'):
    """Inserts an item into the specified DynamoDB table."""
    table = dynamodb.Table(table_name)
    if 'price' in item:
        item['price'] = Decimal(item['price'])  # Ensure price is a Decimal
    try:
        table.put_item(Item=item)
        print(f"Item '{item['id']}' inserted into DynamoDB table '{table_name}'.")
        return True  # Return True on successful insertion
    except ClientError as e:
        print(f"Failed to insert item: {e.response['Error']['Message']}")
        return False  # Return False on failure

        
def get_property_from_dynamodb(property_id):
    """Fetch a property from DynamoDB using its ID."""
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.Table(dynamodb_table_name)
    try:
        response = table.get_item(Key={'id': str(property_id)})
        return response.get('Item', None)
    except ClientError as e:
        logger.error(f"Failed to get property {property_id} from DynamoDB: {e.response['Error']['Message']}")
        return None

def update_property_in_dynamodb(property_item, table_name='ListingTable'):
    """Updates a property item in the specified DynamoDB table."""
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.Table(table_name)

    # Preparing the item for update
    item = {
        'id': str(property_item.id),
        'title': property_item.title,
        'description': property_item.description,
        'image': str(property_item.image),
        'price': Decimal(property_item.price),
    }
    try:
        table.update_item(
            Key={
                'id': item['id']
            },
            UpdateExpression="SET title = :t, description = :d, image = :img, price = :p",
            ExpressionAttributeValues={
                ':t': item['title'],
                ':d': item['description'],
                ':img': item['image'],
                ':p': item['price'],
            }
        )
        print(f"Item '{item['id']}' updated in DynamoDB table '{table_name}'.")
    except ClientError as e:
        print(f"Failed to update item: {e.response['Error']['Message']}")

def get_items_from_dynamodb(table_name='ListingTable'):
    """Get all items from DynamoDB."""
    table = dynamodb.Table(table_name)
    try:
        response = table.scan()
        return response.get('Items', [])
    except ClientError as e:
        logger.error(f"Failed to fetch items from DynamoDB: {e}")
        return []


def delete_property_from_dynamodb(property_id, table_name='ListingTable'):
    """Deletes a property item from the specified DynamoDB table."""
    try:
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.Table(table_name)

        response = table.delete_item(
            Key={
                'id': str(property_id)
            },
            ReturnValues='ALL_OLD'
        )

        if 'Attributes' in response:
            print(f"Successfully deleted property {property_id} from DynamoDB")
            return True
        else:
            print(f"No property found with ID {property_id} in DynamoDB")
            return False
            
    except Exception as e:
        print(f"Error deleting property from DynamoDB: {e}")
        raise
# SNS Section
def create_sns_topic(topic_name='ContactUsTopic'):
    """Create an SNS topic and return its ARN."""
    try:
        response = sns_client.create_topic(Name=topic_name)
        topic_arn = response['TopicArn']
        logging.info(f"SNS Topic created with ARN: {topic_arn}")
        return topic_arn
    except ClientError as e:
        logging.error(f"Failed to create SNS topic: {e.response['Error']['Message']}")
        return None

def subscribe_to_sns(topic_arn, email_address):
    """Subscribe an email address to the SNS topic."""
    try:
        sns_client.subscribe(
            TopicArn=topic_arn,
            Protocol='email',
            Endpoint=email_address
        )
        logging.info(f"Subscription request sent to {email_address}. Please confirm the email.")
    except ClientError as e:
        logging.error(f"Failed to subscribe: {e.response['Error']['Message']}")

def send_email_via_sns(topic_arn, subject, message):
    """Send a message via SNS."""
    try:
        sns_client.publish(
            TopicArn=topic_arn,
            Message=message,
            Subject=subject
        )
        logging.info("SNS message sent successfully.")
    except ClientError as e:
        logging.error(f"Failed to send SNS message: {e.response['Error']['Message']}")

# Helper function for "Contact Us" submissions
def handle_contact_us_submission(user_email, message_content, target_email='gushymushy03@gmail.com'):
    """Handles the contact us form submission and triggers an SNS message."""
    topic_arn = create_sns_topic()

    if topic_arn:
        #subscribe_to_sns(topic_arn, target_email)

        subject = f"New Contact Us Message from {user_email}"
        message = f"User {user_email} sent the following message: \n\n{message_content}"
        send_email_via_sns(topic_arn, subject, message)
