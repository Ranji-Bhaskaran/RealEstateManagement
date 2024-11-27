import boto3
from botocore.exceptions import ClientError
from django.contrib import messages
from django.db import IntegrityError
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from decimal import Decimal
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Property, Favorite, Contact
from django.db.models import Q
from .forms import PropertyForm, ContactForm, CustomUserCreationForm
from .utils import upload_to_s3, delete_item_from_s3, insert_item_to_dynamodb, get_items_from_dynamodb, get_property_from_dynamodb, update_property_in_dynamodb, delete_property_from_dynamodb, handle_contact_us_submission
from io import BytesIO
from django.templatetags.static import static
import logging
#Lambda Imports-----------------------------------------
from .models import Notification
from .lambda_utils import get_user_notifications, mark_notifications_as_read
from decimal import Decimal
#twilio --------------------------------------------------
from django.conf import settings
from twilio.rest import Client
# Library
from returnsage.returncalculator import calculate_returns, calculate_stamp_duty, calculate_admin_fee, calculate_total_cost
from Twilly.whatsappMessage import send_confirmation_message

# AWS Configuration
bucket_name = 'realestate-listing-images'
target_email = 'gushymushy03@gmail.com'

# Logger configuration
logger = logging.getLogger(__name__)


def health_check():
    """ Health check """
    return HttpResponse("OK", status=200)

# Home page view
def home(request):
    if request.user.is_authenticated:
        return redirect('property_list')
    return render(request, 'home.html')

# Register / login
def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('login')
    else:
        form = CustomUserCreationForm()

    return render(request, 'register.html', {'form': form})


def login_view(request):
    error_message = None
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            next_url = request.GET.get('next', 'property_list')
            return redirect(next_url)
        else:
            error_message = "Invalid username or password"
    
    if request.GET.get('error'):
        messages.error(request, "You must log in to access this page.")
    
    return render(request, 'login.html', {'error_message': error_message})

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('home')

@login_required
def property_list(request):
    if not request.user.is_authenticated:
        messages.error(request, "Please log in to access the page.")
        return redirect('home')

    # Get filter values from the GET request, default to empty string if None
    name_query = request.GET.get('name', '')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    description_query = request.GET.get('description', '')

    # Initialize the query set for filtering properties
    properties = Property.objects.all()

    # Apply filters based on the inputs
    if name_query:
        properties = properties.filter(title__icontains=name_query)
    
    if description_query:
        properties = properties.filter(description__icontains=description_query)
    
    # Handle price filtering if min_price or max_price is provided
    if min_price:
        properties = properties.filter(price__gte=min_price)
    if max_price:
        properties = properties.filter(price__lte=max_price)

    # Get favorite property IDs for the logged-in user
    favorite_property_ids = request.user.favorites.values_list('property__id', flat=True)

    return render(request, 'property_list.html', {
        'properties': properties,
        'favorite_property_ids': favorite_property_ids,
        'name_query': name_query if name_query else None,
        'min_price': min_price,
        'max_price': max_price,
        'description_query': description_query if description_query else None,
    })

@login_required
def property_detail(request, property_id):
    property = get_object_or_404(Property, id=property_id)
    is_favorited = Favorite.objects.filter(user=request.user, property=property).exists()
    
    # Pass the owner of the property to the context
    return render(request, 'property_detail.html', {
        'property': property,
        'is_favorited': is_favorited,
        'user': request.user  # This ensures user information is available in the template
    })


@login_required
def post_property(request):
    if request.method == 'POST':
        form = PropertyForm(request.POST, request.FILES)
        
        if form.is_valid():
            # Save form data to get the instance and ID
            property_instance = form.save(commit=False)
            property_instance.owner = request.user
            property_instance.save()  # Ensure ID is set after this call

            # Handle image upload to S3
            image_file = request.FILES.get('image')
            if image_file:
                buffer = BytesIO()
                for chunk in image_file.chunks():
                    buffer.write(chunk)
                buffer.seek(0)
                image_filename = f"{property_instance.title.replace(' ', '_')}.jpg"
                s3_image_url = upload_to_s3(buffer, image_filename, bucket_name="realestate-listing-images")

                if s3_image_url:
                    property_instance.image = s3_image_url
                    property_instance.save()  # Save with image URL
                    
                    # Prepare item data for DynamoDB
                    item = {
                        'id': str(property_instance.id),
                        'title': property_instance.title,
                        'description': property_instance.description,
                        'price': Decimal(str(property_instance.price)),  # Ensure price is Decimal
                        'image': s3_image_url,
                    }

                    # Attempt to insert item into DynamoDB
                    if insert_item_to_dynamodb(item):
                        messages.success(request, "Property posted successfully.")
                        return redirect('property_list')  # Redirect on success
                    else:
                        messages.error(request, "Failed to save property data to DynamoDB.")
                else:
                    messages.error(request, "Failed to upload image to S3.")
            else:
                messages.error(request, "Image file is required.")
    else:
        form = PropertyForm()

    return render(request, 'post_property.html', {'form': form})

    
@login_required
def update_property(request, property_id):
    property_item = get_object_or_404(Property, id=property_id)

    if request.method == 'POST':
        form = PropertyForm(request.POST, request.FILES, instance=property_item)

        if form.is_valid():
            # If a new image is uploaded, handle the S3 upload
            if request.FILES.get('image'):
                # Construct the filename for S3 upload
                filename = f"property_images/{property_item.id}_{request.FILES['image'].name}"
                
                # Upload new image to S3 and get the URL
                new_image_url = upload_to_s3(request.FILES['image'], filename, 'realestate-listing-images')
                
                # Check if the upload was successful
                if new_image_url:
                    # Update the property instance with the new image URL
                    property_item.image = new_image_url
            
            # Save other form fields
            property_item = form.save()  # Make sure to save the form after updating the image URL

            # Update DynamoDB with the new property details
            update_property_in_dynamodb(property_item)

            return redirect('property_detail', property_id=property_item.id)
    else:
        form = PropertyForm(instance=property_item)

    return render(request, 'update_property.html', {'form': form, 'property': property_item})


@login_required
def delete_property(request, property_id):
    # Retrieve the property instance or return a 404 if not found
    property_item = get_object_or_404(Property, id=property_id)

    # Verify ownership of the property
    if property_item.owner != request.user:
        return HttpResponseForbidden("You are not allowed to delete this property.")

    if request.method == 'POST':
        # Attempt to delete the image from S3 if it exists
        if property_item.image:
            try:
                # Use the correct key for deletion, which should match the stored image URL structure
                url_parts = property_item.image.split('/')
                bucket_name = url_parts[2].split('.')[0]  # Extract bucket name
                key = '/'.join(url_parts[3:])  # Construct the key from the URL parts

                delete_item_from_s3(bucket_name, key)  # Call to delete from S3
            except Exception as e:
                messages.error(request, f"Error deleting image from S3: {e}")

        # Attempt to delete the property from DynamoDB
        try:
            delete_property_from_dynamodb(property_id)
        except Exception as e:
            messages.error(request, f"Error deleting from DynamoDB: {e}")
            return redirect('property_list')

        # Delete the property from the Django database
        property_item.delete()
        
        messages.success(request, 'Your property has been deleted successfully!')
        return redirect('property_list')

    # Render a confirmation template if the request is not POST
    return render(request, 'confirm_delete.html', {'property': property_item})

@login_required
def add_favorite(request, property_id):
    property_item = get_property_from_dynamodb(property_id)
    if property_item is None:
        messages.error(request, "Property not found.")
        return redirect('property_list')

    if not Favorite.objects.filter(user=request.user, property_id=property_id).exists():
        try:
            Favorite.objects.create(user=request.user, property_id=property_id)
            messages.success(request, "Added to favorites.")
        except IntegrityError as e:
            logger.error(f"IntegrityError: {str(e)}")
            messages.error(request, "Failed to add to favorites.")

    return redirect('property_detail', property_id=property_id)


@login_required
def remove_favorite(request, property_id):
    property_item = get_property_from_dynamodb(property_id)
    if property_item is None:
        messages.error(request, "Property not found.")
        return redirect('property_list')

    favorite = Favorite.objects.filter(user=request.user, property_id=str(property_item['id']))  # Convert to string
    if favorite.exists():
        favorite.delete()
        messages.success(request, "Removed from favorites.")

    return redirect('property_detail', property_id=property_item['id'])

@login_required
def favorites_list(request):
    favorites = Favorite.objects.filter(user=request.user).select_related('property')
    return render(request, 'favorites_list.html', {'favorites': favorites})


# Contact Us view
def contact_us_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            user_email = form.cleaned_data['email']
            message_content = form.cleaned_data['message']
            handle_contact_us_submission(user_email, message_content)
            messages.success(request, "Your message has been sent successfully.")
            return render(request, 'contact_us.html', {'form': ContactForm(), 'success': True})
    else:
        form = ContactForm()

    return render(request, 'contact_us.html', {'form': form})


#-----------------------------Lambda Functions------------------------------------------------------------------------

@login_required
def notifications_view(request):
    user_id = request.user.id

    # Mark all notifications as read if the request is POST
    if request.method == 'POST':
        mark_notifications_as_read(user_id)  # This will mark all notifications as read
        return redirect('notifications')  # Redirect to avoid form resubmission on page reload

    # Fetch only unread notifications for the user
    notifications = get_user_notifications(user_id)
    
    return render(request, 'notifications.html', {'notifications': notifications})
    
#---------------------Library------------------------------------------------------------------

@login_required
def property_returns(request, property_id):
    # Fetch the property data
    property_item = get_object_or_404(Property, id=property_id)
    total_price = property_item.price
    # Calculate the estimated returns using your library function
    estimated_returns = calculate_returns(Decimal(total_price))

    return render(request, 'property_returns.html', {
        'property': property_item,
        'estimated_returns': estimated_returns,
    })

def checkout(request, property_id):
    # Fetch the property data
    property_item = get_object_or_404(Property, id=property_id)
    price = property_item.price
    price = Decimal(price)

    # Calculate costs using your library functions
    stamp_duty = calculate_stamp_duty(price)
    admin_fee = calculate_admin_fee(price)
    total_cost = calculate_total_cost(price)

    # Pass the calculated values to the template
    context = {
        'property': property_item,
        'price': price,
        'stamp_duty': stamp_duty,
        'admin_fee': admin_fee,
        'total_cost': total_cost,
    }

    return render(request, 'checkout.html', context)

def payment_page(request, property_id):
    property_item = get_object_or_404(Property, id=property_id)
    message_sid = send_confirmation_message(property_item)
    return render(request, 'payment_page.html', {'property': property})
 