from django.conf import settings
from newsapi import NewsApiClient
from groq import Groq
from ...models import Article, ArticleGroq
import logging

logger = logging.getLogger(__name__)

class NewsAPIService:
    """Service for handling NewsAPI interactions."""
    
    def __init__(self):
        self.newsapi = NewsApiClient(api_key=settings.NEWS_API_KEY)
    
    def get_top_headlines(self, query, language='en', country='us'):
        return self.newsapi.get_top_headlines(
            q=query,
            language=language,
            country=country
        )
    
    def get_all_articles(self, query, language='en'):
        return self.newsapi.get_everything(
            q=query,
            language=language,
            sort_by='relevancy'
        )

class GroqAnalysisService:
    """Service for analyzing news articles using Groq."""
    
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
    
    def analyze_article(self, article):
        """Analyze a single article using Groq."""
        if len(article.content) > 8192:
            logger.warning(f"Skipping: {article.title} (content exceeds 8k tokens)")
            return None, 'skipped'
            
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Analyze this article and:"
                        "1. Identify key facts and developments"
                        "2. Provide relevant context"
                        "3. Note any direct quotes"
                        "4. Highlight upcoming important dates"
                        "5. Explain potential implications"
                        "Format for YouTube presentation."
                    )
                },
                {"role": "user", "content": article.content}
            ]
            
            response = self.client.chat.completions.create(
                messages=messages,
                model="mixtral-8x7b-32768",
                temperature=0.5,
                max_tokens=8192,
                top_p=1,
                stream=True
            )
            
            analysis = ""
            for chunk in response:
                delta_content = chunk.choices[0].delta.content or ""
                analysis += delta_content
                
            return analysis, 'processed'
            
        except Exception as e:
            logger.error(f"Error processing {article.title}: {str(e)}")
            return None, 'error'
    
    def save_analysis(self, article, analysis, status):
        """Save the analysis results to the database."""
        return ArticleGroq.objects.create(
            title=article.title,
            polarized_content=analysis,
            url=article.url,
            published_at=article.published_at,
            status=status
        )
