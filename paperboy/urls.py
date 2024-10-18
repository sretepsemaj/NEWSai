# paperboy/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.paperboy_view, name='paperboy'),
]
