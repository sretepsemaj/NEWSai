from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services import NewsAPIService, GroqAnalysisService
from ...models import Article, ArticleGroq
import logging

logger = logging.getLogger(__name__)

def news_view(request):
    """View for fetching news from NewsAPI."""
    news_service = NewsAPIService()
    
    # Get news from both endpoints
    top_headlines = news_service.get_top_headlines('Trump')
    all_articles = news_service.get_all_articles('Trump')
    
    context = {
        'top_headlines': top_headlines['articles'],
        'all_articles': all_articles['articles']
    }
    
    return render(request, 'news.html', context)

@csrf_exempt
def article_groq_view(request):
    """View for analyzing articles with Groq."""
    # Initialize services
    groq_service = GroqAnalysisService()
    
    # Get unprocessed articles
    articles = Article.objects.filter(title__icontains='Trump').first()
    
    if not articles:
        logger.warning("No articles found for analysis.")
        return render(request, "groq.html", {"error": "No articles found."})
    
    success_count = 0
    skipped_count = 0
    
    # Process the article
    analysis, status = groq_service.analyze_article(articles)
    
    if status == 'processed':
        groq_service.save_analysis(articles, analysis, status)
        success_count += 1
    else:
        skipped_count += 1
    
    # Get all processed articles for display
    processed_articles = ArticleGroq.objects.all()
    
    context = {
        "articles": processed_articles,
        "success_count": success_count,
        "skipped_count": skipped_count,
    }
    
    return render(request, "groq.html", context)

def fetch_and_save_articles():
    """Background task to fetch and save articles."""
    news_service = NewsAPIService()
    
    # Fetch articles
    headlines = news_service.get_top_headlines('Trump')
    articles = news_service.get_all_articles('Trump')
    
    # Combine and deduplicate articles
    all_articles = headlines['articles'] + articles['articles']
    unique_articles = {article['url']: article for article in all_articles}.values()
    
    # Save to database
    saved_count = 0
    for article_data in unique_articles:
        try:
            Article.objects.get_or_create(
                url=article_data['url'],
                defaults={
                    'title': article_data['title'],
                    'content': article_data.get('content', ''),
                    'description': article_data.get('description', ''),
                    'author': article_data.get('author', ''),
                    'source': article_data.get('source', {}).get('name', ''),
                    'published_at': article_data['publishedAt'],
                    'image_url': article_data.get('urlToImage', '')
                }
            )
            saved_count += 1
        except Exception as e:
            logger.error(f"Error saving article {article_data['url']}: {str(e)}")
    
    return saved_count

def articles_list_view(request):
    """View to display all saved articles."""
    articles = Article.objects.all().order_by('-published_at')
    return render(request, 'articles_list.html', {'articles': articles})
