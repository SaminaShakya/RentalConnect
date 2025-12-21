# users urls (create users/urls.py)
from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.update_profile, name='update_profile'),


]
