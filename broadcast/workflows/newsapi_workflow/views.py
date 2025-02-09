from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .services import NewsAPIService, GroqAnalysisService
from ...models import Article, ArticleGroq
import logging
from datetime import datetime
import json

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

def article_detail_view(request, article_id):
    """View to display detailed article information."""
    # Get the article and its related Groq analysis
    article = get_object_or_404(Article, id=article_id)
    groq_analysis = ArticleGroq.objects.filter(url=article.url).first()
    
    context = {
        'article': article,
        'groq_analysis': groq_analysis,
        'has_analysis': groq_analysis is not None
    }
    
    return render(request, 'article_detail.html', context)

@csrf_exempt
@require_http_methods(["POST"])
def generate_article_analysis(request, article_id):
    """Generate Groq analysis for a specific article."""
    try:
        # Get the article
        article = get_object_or_404(Article, id=article_id)
        
        # Check if analysis already exists
        existing_analysis = ArticleGroq.objects.filter(url=article.url).first()
        if existing_analysis:
            return JsonResponse({
                'status': 'success',
                'message': 'Analysis already exists',
                'analysis': existing_analysis.polarized_content
            })
        
        # Initialize Groq service
        groq_service = GroqAnalysisService()
        
        # Generate analysis
        analysis, status = groq_service.analyze_article(article)
        
        if status == 'processed':
            # Save the analysis
            groq_analysis = groq_service.save_analysis(article, analysis, status)
            
            return JsonResponse({
                'status': 'success',
                'message': 'Analysis generated successfully',
                'analysis': analysis
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to generate analysis',
                'error': 'Content processing failed'
            }, status=500)
            
    except Exception as e:
        logger.error(f"Error generating analysis for article {article_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

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

@csrf_exempt
def fetch_and_save_articles(request):
    """View to fetch and save articles."""
    try:
        news_service = NewsAPIService()
        
        # Fetch articles
        headlines = news_service.get_top_headlines('Trump')
        articles = news_service.get_all_articles('Trump')
        
        # Combine and deduplicate articles
        all_articles = headlines['articles'] + articles['articles']
        unique_articles = {article['url']: article for article in all_articles}.values()
        
        # Process and save each article
        saved_count = 0
        failed_count = 0
        
        for article_data in unique_articles:
            article, is_new = news_service.process_and_save_article(article_data)
            if article and is_new:
                saved_count += 1
            elif not article:
                failed_count += 1
        
        return JsonResponse({
            'status': 'success',
            'message': f'Successfully saved {saved_count} new articles ({failed_count} failed)',
            'saved_count': saved_count,
            'failed_count': failed_count
        })
        
    except Exception as e:
        logger.error(f"Error in fetch_and_save_articles: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

def articles_list_view(request):
    """View to display all saved articles."""
    articles = Article.objects.all().order_by('-published_at')
    
    # Get all analyses and create a dictionary of article URLs to analysis data
    analyses = ArticleGroq.objects.all()
    analysis_dict = {}
    for analysis in analyses:
        analysis_dict[analysis.url] = {
            'content': analysis.polarized_content,
            'status': analysis.status
        }
    
    # Add analysis data to each article
    articles_with_analysis = []
    for article in articles:
        article_data = {
            'article': article,
            'analysis': analysis_dict.get(article.url, None)
        }
        articles_with_analysis.append(article_data)
    
    return render(request, 'articles_list.html', {
        'articles_data': articles_with_analysis
    })

@require_http_methods(["POST"])
def delete_articles(request):
    """View to delete all articles."""
    try:
        # Delete all articles
        Article.objects.all().delete()
        # Also delete related Groq analyses
        ArticleGroq.objects.all().delete()
        
        return JsonResponse({
            'status': 'success',
            'message': 'All articles deleted successfully'
        })
    except Exception as e:
        logger.error(f"Error deleting articles: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
