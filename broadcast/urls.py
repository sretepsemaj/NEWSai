from django.urls import path
from django.conf import settings  # Import settings
from django.conf.urls.static import static  # Import static to serve media files
from . import views

urlpatterns = [
    path('', views.index_view, name='index'),
    path('reporter/', views.reporter_view, name='reporter'),
    path('director/', views.director_view, name='director'),
    path('anchorman/', views.anchorman_view, name='anchorman'),
    path('news/', views.news_view, name='news'),
    path('fetch-articles/', views.fetch_articles_view, name='fetch_articles_view'),  # Ensure this line is correct
    path('articles/', views.articles_list_view, name='articles_list'),  # No 'broadcast/' prefix needed
    path('generate-embed/', views.generate_embedding_view, name='generate_embedding_view'),  # Update to the correct view name
    path('groq/', views.article_groq_view, name='article_groq'),
    path('republic/', views.article_republic_view, name='article_republic_view'),
    path('democratic/', views.article_democratic_view, name='article_democratic_view'),
    ]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
