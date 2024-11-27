from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  # Home page
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('properties/', views.property_list, name='property_list'),  # Buy
    path('post_property/', views.post_property, name='post_property'),  # Sell
    path('properties/<str:property_id>/', views.property_detail, name='property_detail'),  # Detail view
    path('properties/<int:property_id>/update/', views.update_property, name='update_property'), # Update property
    path('delete_property/<int:property_id>/', views.delete_property, name='delete_property'),  # Delete listing
    path('favorites/', views.favorites_list, name='favorites_list'),  # Favorites list
    path('add_favorite/<int:property_id>/', views.add_favorite, name='add_favorite'),
    path('remove_favorite/<int:property_id>/', views.remove_favorite, name='remove_favorite'),
    path('contact-us/', views.contact_us_view, name='contact-us'),
    #------------------LambdaUrls-----------------------------------
    path('notifications/', views.notifications_view, name='notifications'),
    #-----------------------Library--------------------------
    path('property/<int:property_id>/returns/', views.property_returns, name='property_returns'),
    path('checkout/<int:property_id>/', views.checkout, name='checkout'),
    
    #twilio ----------------------------------------------------------------------
    path('confirm_payment/<int:property_id>/', views.payment_page, name='confirm_payment'),
]
