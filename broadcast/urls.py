from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .workflows.perplexity_workflow import views as perplexity_views
from .workflows.newsapi_workflow import views as newsapi_views

app_name = 'broadcast'  # Add namespace

urlpatterns = [
    # Perplexity Workflow URLs
    path('', perplexity_views.reporter_view, name='index'),
    path('reporter/', perplexity_views.reporter_view, name='reporter'),
    path('director/', perplexity_views.director_view, name='director'),
    path('anchorman/', perplexity_views.anchorman_view, name='anchorman'),
    
    # NewsAPI Workflow URLs
    path('news/', newsapi_views.news_view, name='news'),
    path('fetch-articles/', newsapi_views.fetch_and_save_articles, name='fetch_articles'),
    path('articles/', newsapi_views.articles_list_view, name='articles_list'),
    path('articles/<int:article_id>/', newsapi_views.article_detail_view, name='article_detail'),
    path('articles/<int:article_id>/analyze/', newsapi_views.generate_article_analysis, name='generate_analysis'),
    path('groq/', newsapi_views.article_groq_view, name='article_groq'),
    path('delete-articles/', newsapi_views.delete_articles, name='delete_articles'),
]

# Only add static patterns if DEBUG is True
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
