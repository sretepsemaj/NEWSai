import openai
import json
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.utils.cache import patch_response_headers
from django.views.decorators.csrf import csrf_exempt
import requests 
import tempfile
import shutil
from datetime import datetime
from .models import Article
from bs4 import BeautifulSoup
from django.utils import timezone
import logging
from django.db import transaction
import os

logger = logging.getLogger(__name__)

def index_view(request):
    return render(request, 'broadcast/index.html')
def home_view(request):
    return render(request, 'broadcast/home.html')

@csrf_exempt
def reporter_view(request):
    if request.method == 'POST':
        try:
            # Get the user query from the form
            user_query = request.POST.get('query', '')

            if not user_query:
                return render(request, 'broadcast/reporter.html', {'error': 'Please enter a query.'})

            # Payload to send to the PLEX API
            payload = {
                "model": "sonar-reasoning-pro",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful news assistant. Find relevant news stories and their sources based on the user's query. Summarize them objectively and cite your sources."
                    },
                    {
                        "role": "user",
                        "content": user_query
                    }
                ]
            }

            # Make the API call to PLEX
            response = requests.post(
                settings.PLEX_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.PLEX_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload
            )

            # Handle the API response
            if response.status_code == 200:
                api_data = response.json()
                logger.info(f"API Response: {api_data}")
                # Extract the story content
                content = api_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # Remove the <think> section if present
                if '<think>' in content and '</think>' in content:
                    think_end = content.find('</think>') + len('</think>')
                    story = content[think_end:].strip()
                else:
                    story = content

                logger.info(f"Extracted story: {story}")

                # Save the story in the session
                request.session['news_story'] = story

                # Return JSON response for AJAX request
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'story': story})
                
                # Render the reporter page with the generated story for non-AJAX request
                return render(request, 'broadcast/reporter.html', {'story': story})
            else:
                # Handle API errors
                error_message = f"API Error: {response.status_code} - {response.text}"
                logger.error(error_message)  # Log the error message
                return render(request, 'broadcast/reporter.html', {'error': error_message})

        except Exception as e:
            # Handle any unexpected errors
            return render(request, 'broadcast/reporter.html', {'error': str(e)})

    # Handle GET request, display any existing story from the session
    story = request.session.get('news_story', '')
    return render(request, 'broadcast/reporter.html', {'story': story})



@never_cache
def director_view(request):
    reporter_response = request.session.get('news_story', 'No data available from the reporter')

    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            if data.get('action') == 'generate_script':
                if not reporter_response:
                    return JsonResponse({'error': 'No data available from the reporter'}, status=400)

                # Set up OpenAI API key
                client = openai.OpenAI(api_key=settings.MYSK_API_KEY)

                # Use the new API format
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Write a teleprompter script as official as it would be on the nightly news."},
                        {"role": "user", "content": f"Create a concise teleprompter but be objective and cover both sides of the script:\n\n{reporter_response}"}
                    ],
                    max_tokens=200,
                    temperature=0.7
                )

                teleprompter_script = response.choices[0].message.content.strip()
                request.session['teleprompter_script'] = teleprompter_script

                return JsonResponse({'teleprompter_script': teleprompter_script})
            else:
                return JsonResponse({'error': 'Invalid action'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            print(f"API call error: {str(e)}")
            return JsonResponse({'error': f"API call failed: {str(e)}"}, status=500)

    teleprompter_script = request.session.get('teleprompter_script', '')

    return render(request, 'broadcast/director.html', {
        'reporter_response': reporter_response,
        'teleprompter_script': teleprompter_script,
    })

def generate_speech(text, voice="onyx"):
    try:
        # Create OpenAI client
        client = openai.OpenAI(api_key=settings.MYSK_API_KEY)
        
        # Create speech using OpenAI API
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )
        
        # Create a temporary file to save the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
            response.stream_to_file(temp_file.name)
            
            # Create the media directory if it doesn't exist
            media_dir = os.path.join(settings.MEDIA_ROOT, 'speech')
            os.makedirs(media_dir, exist_ok=True)
            
            # Generate a unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'speech_{timestamp}.mp3'
            filepath = os.path.join(media_dir, filename)
            
            # Copy the temporary file to the media directory
            shutil.copy2(temp_file.name, filepath)
        
        # Return the URL path to the audio file
        return os.path.join(settings.MEDIA_URL, 'speech', filename)
        
    except Exception as e:
        print(f"Speech generation error: {str(e)}")
        return None

@csrf_exempt
def anchorman_view(request):
    script = request.session.get('teleprompter_script', 'No script available')

    if not script:
        return render(request, 'broadcast/anchorman.html', {'error': 'No teleprompter script found'})

    if request.method == 'POST':
        filename = generate_speech(script)
        if filename:
            mp3_url = filename  # Use only filename, not full temp path
            request.session['mp3_url'] = mp3_url  # Store the URL in the session
            return JsonResponse({'mp3_url': mp3_url})
        else:
            return JsonResponse({'error': 'Failed to generate speech'}, status=500)

    # Render the Anchorman page with the script and MP3 if it exists
    mp3_url = request.session.get('mp3_url', '')
    return render(request, 'broadcast/anchorman.html', {
        'script': script,
        'mp3_url': mp3_url
    })


def fetch_full_article_content(url):
    """Fetch the full content of the article from its URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Check for request errors

        soup = BeautifulSoup(response.content, 'html.parser')

        # Assuming the full content is within an <article> tag or similar
        full_content = soup.find('article').get_text(strip=True) if soup.find('article') else "Content not found."
        
        return full_content
    except Exception as e:
        logger.error(f"Error fetching full article content from {url}: {e}")
        return "Error Fetching Full Content"  # Fallback for errors


def article_view(request):
    api_key = settings.NEWS_API_KEY
    url = f'https://newsapi.org/v2/everything?q=American politics&language=en&apiKey={api_key}'
    response = requests.get(url)

    if response.status_code != 200:
        logger.error(f"Error fetching articles: {response.status_code} {response.text}")
        return render(request, 'article.html', {'error': 'Could not fetch articles at this time.'})

    try:
        articles = response.json().get('articles', [])
        logger.info(f"Fetched {len(articles)} articles.")
    except ValueError as e:
        logger.error(f"Error decoding JSON: {e}")
        return render(request, 'article.html', {'error': 'Could not decode article data.'})

    # Process articles
    for article in articles:
        published_at = datetime.fromisoformat(article.get('publishedAt')[:-1])
        published_at = timezone.make_aware(published_at)  # Make it timezone-aware
        article_url = article.get('url')

        # Get initial metadata to save
        title = article.get('title')
        source = article.get('source', {}).get('name')
        description = article.get('description')

        # Fetch the full content from the article URL
        content = fetch_full_article_content(article_url)

        # Save or update the article in the database within a transaction
        with transaction.atomic():
            Article.objects.update_or_create(
                title=title,
                source=source,
                url=article_url,
                published_at=published_at,
                description=description,
                content=content  # Save the full content from scraping
            )

    # Retrieve saved articles to display
    saved_articles = Article.objects.all()
    context = {'articles': saved_articles}
    return render(request, 'article.html', context)

def articles_view(request):
    """View to display list of broadcast articles"""
    articles = Article.objects.all().order_by('-published_at')  # Get all articles, newest first
    return render(request, 'broadcast/articles.html', {'articles': articles})
