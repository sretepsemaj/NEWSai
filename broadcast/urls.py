from django.urls import path
from django.conf import settings  # Import settings
from django.conf.urls.static import static  # Import static to serve media files
from . import views
from .views import article_view

urlpatterns = [
    path('', views.index_view, name='index'),
    path('reporter/', views.reporter_view, name='reporter'),
    path('director/', views.director_view, name='director'),
    path('anchorman/', views.anchorman_view, name='anchorman'),
    path('article/', article_view, name='article_view'),
    path('articles/', views.articles_view, name='articles'),  # Added articles URL pattern
]

# Add this to serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
