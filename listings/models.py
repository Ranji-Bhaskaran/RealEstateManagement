from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MaxLengthValidator

class Property(models.Model):
    # id is now an auto-incremented integer by default in Django
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    location = models.CharField(max_length=100)
    image = models.ImageField(upload_to='property_images/')
    posted_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='favorited_by')

    class Meta:
        unique_together = ('user', 'property')

class Contact(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField(validators=[MaxLengthValidator(1000)])  # Limit message to 1000 characters
    date_submitted = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

#------------------------------------------ Model for Notification
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    property_id = models.ForeignKey(Property, on_delete=models.CASCADE)
    message = models.TextField()
    is_read = models.BooleanField(default=False)  # Marks whether the notification has been read by the user
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.username} - {self.property.title} - Read: {self.is_read}"
