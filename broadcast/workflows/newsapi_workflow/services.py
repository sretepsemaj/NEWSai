from django.conf import settings
from newsapi import NewsApiClient
from groq import Groq
from ...models import Article, ArticleGroq
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import tiktoken

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
    
    def fetch_full_content(self, url):
        """Fetch the full content of an article from its URL."""
        try:
            # Some common news sites block basic requests, so we'll use a more browser-like header
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'iframe']):
                element.decompose()
            
            # Try different methods to find the main content
            content = ""
            
            # Method 1: Look for article tag
            article = soup.find('article')
            if article:
                content = self._extract_text_from_element(article)
            
            # Method 2: Look for main content div
            if not content:
                main_content = soup.find(['main', 'div'], class_=lambda x: x and any(term in x.lower() for term in ['content', 'article', 'story', 'body']))
                if main_content:
                    content = self._extract_text_from_element(main_content)
            
            # Method 3: Fallback to all paragraphs
            if not content:
                paragraphs = soup.find_all('p')
                content = ' '.join(p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 50)
            
            # Get the title
            title = None
            # Try h1 first
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text().strip()
            # Fallback to title tag
            if not title:
                title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.get_text().strip()
            
            return {
                'title': title,
                'content': content,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error fetching content from {url}: {str(e)}")
            return {
                'title': None,
                'content': None,
                'success': False,
                'error': str(e)
            }
    
    def _extract_text_from_element(self, element):
        """Helper method to extract clean text from an HTML element."""
        # Get all paragraphs
        paragraphs = element.find_all('p')
        
        # Filter out short paragraphs (likely to be ads or other unwanted content)
        valid_paragraphs = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 50]
        
        return ' '.join(valid_paragraphs)
    
    def process_and_save_article(self, article_data):
        """Process and save a single article with full content."""
        try:
            # First, check if we already have this article
            existing_article = Article.objects.filter(url=article_data['url']).first()
            if existing_article:
                logger.info(f"Article already exists: {article_data['url']}")
                return existing_article, False
            
            # Fetch full content
            full_content = self.fetch_full_content(article_data['url'])
            
            if full_content['success']:
                # Create the article with the fetched content
                article = Article.objects.create(
                    title=full_content['title'] or article_data['title'],
                    url=article_data['url'],
                    source=article_data.get('source', {}).get('name', ''),
                    content=full_content['content'],
                    description=article_data.get('description', ''),
                    author=article_data.get('author', ''),
                    published_at=article_data['publishedAt'],
                    image_url=article_data.get('urlToImage', '')
                )
                logger.info(f"Successfully saved article with full content: {article.url}")
                return article, True
            else:
                # If content fetch failed, save with original data
                article = Article.objects.create(
                    title=article_data['title'],
                    url=article_data['url'],
                    source=article_data.get('source', {}).get('name', ''),
                    content=article_data.get('content', ''),
                    description=article_data.get('description', ''),
                    author=article_data.get('author', ''),
                    published_at=article_data['publishedAt'],
                    image_url=article_data.get('urlToImage', '')
                )
                logger.warning(f"Saved article with limited content: {article.url}")
                return article, True
                
        except Exception as e:
            logger.error(f"Error processing article {article_data.get('url', 'Unknown URL')}: {str(e)}")
            return None, False

class GroqAnalysisService:
    """Service for analyzing news articles using Groq."""
    
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self.max_tokens = 4000  # Reduced from 8000 to stay well under rate limits
        self.chunk_overlap = 200  # Reduced overlap to save tokens
        self.max_output_tokens = 1000  # Limit response size
    
    def count_tokens(self, text):
        """Count the number of tokens in a text."""
        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            logger.error(f"Error counting tokens: {str(e)}")
            return len(text) // 4
    
    def split_text(self, text):
        """Split text into chunks that fit within token limit."""
        try:
            tokens = self.encoding.encode(text)
            chunks = []
            
            # Calculate chunk size in tokens
            chunk_size = self.max_tokens
            
            # Split into chunks with overlap
            for i in range(0, len(tokens), chunk_size - self.chunk_overlap):
                chunk_tokens = tokens[i:i + chunk_size]
                chunk_text = self.encoding.decode(chunk_tokens)
                chunks.append(chunk_text)
            
            # If chunks are still too large, split them further
            final_chunks = []
            for chunk in chunks:
                token_count = self.count_tokens(chunk)
                if token_count > self.max_tokens:
                    # Split into smaller sub-chunks
                    sub_chunks = [chunk[i:i + 2000] for i in range(0, len(chunk), 2000)]
                    final_chunks.extend(sub_chunks)
                else:
                    final_chunks.append(chunk)
            
            return final_chunks
            
        except Exception as e:
            logger.error(f"Error splitting text: {str(e)}")
            # Fallback to simple character-based chunking with smaller chunks
            chunk_size = 2000  # Approximately 500 tokens
            return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    
    def analyze_chunk(self, chunk, is_first_chunk=False, is_last_chunk=False):
        """Analyze a single chunk of text."""
        try:
            # First, check chunk size
            token_count = self.count_tokens(chunk)
            if token_count > self.max_tokens:
                logger.warning(f"Chunk too large ({token_count} tokens), truncating...")
                tokens = self.encoding.encode(chunk)[:self.max_tokens]
                chunk = self.encoding.decode(tokens)
            
            # Customize the prompt based on chunk position
            if is_first_chunk:
                system_prompt = (
                    "Create a concise YouTube script introduction for this news article. Cover:\n"
                    "1. Main topic and key players (1-2 sentences)\n"
                    "2. Quick context (1-2 sentences)\n"
                    "3. Why viewers should care (1 sentence)\n"
                    "Keep it engaging and brief."
                )
            elif is_last_chunk:
                system_prompt = (
                    "Create a concise YouTube script conclusion for this news article. Cover:\n"
                    "1. Key takeaway (1 sentence)\n"
                    "2. Main implication (1 sentence)\n"
                    "3. Call to action for viewers (1 sentence)\n"
                    "Keep it punchy and memorable."
                )
            else:
                system_prompt = (
                    "Create a concise YouTube script segment for this news article. Cover:\n"
                    "1. Key development (1-2 sentences)\n"
                    "2. Supporting detail (1 sentence)\n"
                    "3. Quick context if needed (1 sentence)\n"
                    "Keep it flowing and clear."
                )
            
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {"role": "user", "content": chunk}
            ]
            
            response = self.client.chat.completions.create(
                messages=messages,
                model="mixtral-8x7b-32768",
                temperature=0.5,
                max_tokens=self.max_output_tokens,
                top_p=1,
                stream=True
            )
            
            analysis = ""
            for chunk in response:
                delta_content = chunk.choices[0].delta.content or ""
                analysis += delta_content
            
            return analysis
            
        except Exception as e:
            if "rate_limit_exceeded" in str(e):
                logger.warning("Rate limit exceeded, waiting before retry...")
                import time
                time.sleep(5)  # Wait 5 seconds before next chunk
                return None
            logger.error(f"Error processing chunk: {str(e)}")
            return None
    
    def analyze_article(self, article):
        """Analyze a news article, handling large content by chunking."""
        try:
            content = article.content
            token_count = self.count_tokens(content)
            
            if token_count <= self.max_tokens:
                # If content fits in one chunk, process normally
                analysis = self.analyze_chunk(content, is_first_chunk=True, is_last_chunk=True)
                if not analysis:
                    return None, 'error'
                return analysis, 'processed'
            
            # Split into chunks if content is too large
            chunks = self.split_text(content)
            analyses = []
            
            # Process each chunk with rate limit handling
            for i, chunk in enumerate(chunks):
                is_first = i == 0
                is_last = i == len(chunks) - 1
                
                # Try up to 3 times for each chunk
                for attempt in range(3):
                    chunk_analysis = self.analyze_chunk(chunk, is_first, is_last)
                    if chunk_analysis:
                        analyses.append(chunk_analysis)
                        break
                    elif attempt < 2:
                        import time
                        time.sleep(5)  # Wait between retries
                    else:
                        logger.error(f"Failed to analyze chunk after 3 attempts")
                
            if analyses:
                # Combine analyses with section headers
                combined_analysis = "\n\n".join([
                    "🎥 NEWS ANALYSIS SUMMARY 🎥\n",
                    "📰 INTRODUCTION",
                    analyses[0],
                    *[f"\n📍 KEY POINTS - PART {i+2}" for i, analysis in enumerate(analyses[1:-1])],
                    *analyses[1:-1],
                    "\n🎯 CONCLUSION",
                    analyses[-1],
                    "\n📌 END OF ANALYSIS 📌"
                ])
                
                return combined_analysis, 'processed'
            
            return None, 'error'
            
        except Exception as e:
            logger.error(f"Error analyzing article {article.title}: {str(e)}")
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
