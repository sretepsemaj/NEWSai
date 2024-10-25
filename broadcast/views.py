import os
import openai
import json
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.utils.cache import patch_response_headers
from django.views.decorators.csrf import csrf_exempt
import requests 
import tempfile
import shutil
from newsapi import NewsApiClient
from bs4 import BeautifulSoup
from datetime import datetime
from .models import Article, ArticleEmbedding, ArticleGroq
from django.utils import timezone
from sentence_transformers import SentenceTransformer
from groq import Groq
import logging

# Initialize the logger at the top of the file
logger = logging.getLogger(__name__)

newsapi = NewsApiClient(api_key=settings.NEWS_API_KEY)

client = Groq(api_key=settings.GROQ_API_KEY)

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
    "model": "llama-3.1-sonar-small-128k-online",
    "messages": [
        {
            "role": "system",
            "content": "adress the user everytime and find them two stories of opposing political views and let the user know that your doing that. make sure to give a source for the information from both side the republicans and the democrats. your a repoorter and take your role very serious making sure that your able to source all your information."
        },
        {
            "role": "user",
            "content": "users name is techmaster tim  mr. TT and rumer has it he is the best coder on the plant. although not confirmend since he only does things on the youtube."
        }
    ],
    "max_tokens": "500",
    "temperature": 0.2,
    "top_p": 0.9,
    "return_citations": True,
    "search_domain_filter": ["perplexity.ai"],
    "return_images": False,
    "return_related_questions": False,
    "search_recency_filter": "month",
    "top_k": 0,
    "stream": False,
    "presence_penalty": 0,
    "frequency_penalty": 1
}

            # Make the API call to PLEX
            response = requests.post(
                settings.PLEX_API_URL,
                headers={"Authorization": f"Bearer {settings.PLEX_API_KEY}"},
                json=payload
            )

            # Handle the API response
            if response.status_code == 200:
                api_data = response.json()
                # Ensure the response has the 'content' key
                story = api_data.get('choices', [{}])[0].get('message', {}).get('content', 'No story found.')

                # Save the story in the session
                request.session['news_story'] = story

                # Render the reporter page with the generated story
                return render(request, 'broadcast/reporter.html', {'story': story})
            else:
                # Handle API errors
                error_message = f"API Error: {response.status_code} - {response.text}"
                return render(request, 'broadcast/reporter.html', {'error': error_message})

        except Exception as e:
            # Handle any unexpected errors
            return render(request, 'broadcast/reporter.html', {'error': str(e)})

    # Handle GET request, display any existing story from the session
    story = request.session.get('news_story', '')
    return render(request, 'broadcast/reporter.html', {'story': story})

def generate_embedding_view(request):
    # Load the embedding model
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Fetch all articles from the database
    articles = Article.objects.all()
    embeddings_results = []

    for article in articles:
        # Prepare the input text for embedding
        input_text = f"Title: {article.title}\nContent: {article.content}\nURL: {article.url}\nDate Extracted: {article.date_extracted}"

        # Check the length of the input text
        if len(input_text) > 512:  # Typical limit for many transformer models
            input_text = input_text[:512]  # Truncate to the first 512 characters

        # Generate the embedding
        embedding = model.encode(input_text)

        # Store the embedding in the ArticleEmbedding model
        ArticleEmbedding.objects.update_or_create(
            article=article,  # The Article instance
            defaults={'vector': embedding.tolist()}  # Convert the embedding to a list and store
        )

        # Append the article and its embedding result to the list
        embeddings_results.append({
            'article': article,
            'embedding': embedding.tolist()  # Store the embedding for rendering
        })

    # Render the results in a template
    return render(request, 'embed.html', {
        'embeddings_results': embeddings_results
    })

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
                openai.api_key = settings.MYSK_API_KEY

                # Use the new API format
                
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Write a teleprompter script as official as it would be on the nightly news tleprompter and remeber the anchorman name is tech with tim."},
                        {"role": "user", "content": f"need this teleprompter for tech with tim:\n\n{reporter_response}"}
                    ],
                    max_tokens=200,  # Adjust the number of tokens based on your requirements
                    temperature=0.7  # Optional: Controls the randomness of the response
                )


                teleprompter_script = response['choices'][0]['message']['content'].strip()
                request.session['teleprompter_script'] = teleprompter_script

                return JsonResponse({'teleprompter_script': teleprompter_script})
            else:
                return JsonResponse({'error': 'Invalid action'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            print(f"API call error: {str(e)}")
            return JsonResponse({'error': f"API call failed: {str(e)}"}, status=500)

    teleprompter_script = request.session.get('teleprompter_script', 'No teleprompter script available')

    response = render(request, 'broadcast/director.html', {
        'reporter_response': reporter_response,
        'teleprompter_script': teleprompter_script,
    })
    return response

def generate_speech(text, voice="onyx"):
    try:
        # Prepare payload for the API
        payload = {
            "model": "tts-1",
            "input": text,
            "voice": voice
        }

        # Set headers with API key
        headers = {
            "Authorization": f"Bearer {settings.MYSK_API_KEY}",
            "Content-Type": "application/json"
        }

        # Make the API call
        response = requests.post(
            "https://api.openai.com/v1/audio/speech",  # Explicit endpoint
            json=payload,
            headers=headers
        )

        # Check for a valid response
        if response.status_code == 200:
            # Generate filename and path
            filename = f"{text[:10].replace(' ', '_')}.mp3"
            media_path = os.path.join(settings.MEDIA_ROOT, filename)

            # Save the audio content to MEDIA_ROOT
            with open(media_path, "wb") as f:
                f.write(response.content)

            return filename  # Return the filename

        else:
            print(f"API Error: {response.status_code} - {response.text}")
            return None  # Handle unsuccessful responses

    except Exception as e:
        print(f"Error generating speech: {str(e)}")
        return None

@csrf_exempt
def anchorman_view(request):
    script = request.session.get('teleprompter_script', 'No script available')

    if not script:
        return render(request, 'broadcast/anchorman.html', {'error': 'No teleprompter script found'})

    if request.method == 'POST':
        filename = generate_speech(script)
        if filename:
            mp3_url = settings.MEDIA_URL + filename  # Use only filename, not full temp path
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

def news_view(request):
    # Fetch top headlines related to American elections
    top_headlines = newsapi.get_top_headlines(q='American election',
                                              language='en',
                                              country='us')

    # Fetch all articles related to American elections (optional)
    all_articles = newsapi.get_everything(q='American election',
                                          language='en',
                                          sort_by='relevancy')

    # Pass the fetched articles to the template
    context = {
        'top_headlines': top_headlines['articles'],  # Extracting the articles
        'all_articles': all_articles['articles']     # Extracting all articles
    }
    
    return render(request, 'news.html', context)

def article_detail(request, url):
    # Fetch article content from the provided URL
    response = requests.get(url)
    
    if response.status_code == 200:
        content = response.text  # Get the HTML content of the article
    else:
        content = "Could not retrieve article content."

    # Pass the content to the template
    return render(request, 'article_detail.html', {'content': content})

def fetch_and_save_articles():
    """Fetch articles from the news page and save them to the database."""
    print("Fetching articles from the news page...")
    url = "http://127.0.0.1:8000/broadcast/news/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error for bad responses
        print("Successfully fetched the news page.")

        soup = BeautifulSoup(response.content, 'html.parser')
        articles = soup.find_all('li')  # Adjust based on your HTML structure
        print(f"Found {len(articles)} articles.")

        for article in articles:
            title_element = article.find('a')
            if not title_element:
                print("No title element found, skipping this article.")
                continue

            title = title_element.text.strip()
            link = title_element['href']
            print(f"Processing article: {title} | Link: {link}")

            # Fetch article details
            article_title, article_content = fetch_article_content(link)

            if article_title and article_content:
                # Save to database
                Article.objects.create(
                    title=article_title,
                    source='Unknown source',  # Default or extract from content if needed
                    content=article_content,
                    published_at=timezone.now(),  # Use timezone-aware now
                    author='Unknown',  # Default or extract if available
                    url=link,
                    description='No description',  # Default or extract if available
                    image_url='No image',  # Default or extract if available
                    keywords='No keywords'  # Default or extract if available
                )
                print(f"Successfully saved article: {title}")
            else:
                print(f"Failed to fetch content for article: {title}")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while making the request: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    print("Finished fetching and saving articles.")

def fetch_article_content(url):
    """Fetch the title and content of a single article."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        title_tag = soup.find('h1')
        title = title_tag.text.strip() if title_tag else "Title not found"

        paragraphs = soup.find_all('p')
        content = ' '.join([para.text.strip() for para in paragraphs if para.text.strip()])

        return title, content

    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None, None

def fetch_articles_view(request):
    """View to fetch and save articles, then render a success page."""
    fetch_and_save_articles()
    
    # Render the success template if fetching was successful
    try:
        return render(request, 'fetch_success.html')  # Ensure fetch_success.html exists
    except TemplateDoesNotExist:
        print("Template 'fetch_success.html' does not exist.")
        return render(request, 'error.html', {'message': "Template not found."})
    
def articles_list_view(request):
    articles = Article.objects.all()  # Fetch all articles from the database
    return render(request, 'articles_list.html', {'articles': articles})  # Render the articles list template

def article_groq_view(request):
    # Retrieve all articles from the Article model
    articles = Article.objects.all()

    # Counters to track progress
    success_count = 0
    skipped_count = 0

    # Loop through the articles and process them
    for article in articles:
        logger.info(f"Processing: {article.title} - {article.content[:50]}...")

        # Check if the article fits within the 8k token limit
        if len(article.content) > 8192:
            logger.warning(f"Skipping: {article.title} (content exceeds 8k tokens)")
            ArticleGroq.objects.create(
                title=article.title,
                polarized_content=None,
                url=article.url,
                published_at=article.published_at,
                status='skipped'
            )
            skipped_count += 1
            continue

        try:
            # Prepare the API request payload
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant. Take the following article "
                        "and break it down into its most important key components. "
                        "Label the information based on whether it aligns with "
                        "Republican or Democratic viewpoints, focusing on polarized "
                        "yet objective details."
                    ),
                },
                {"role": "user", "content": article.content},
            ]

            # Call the Groq API
            response = client.chat.completions.create(
                messages=messages,
                model="mixtral-8x7b-32768",
                temperature=0.5,
                max_tokens=8192,
                top_p=1,
                stream=True,
            )

            # Collect the response in chunks
            polarized_summary = ""
            for chunk in response:
                delta_content = chunk.choices[0].delta.content or ""
                polarized_summary += delta_content

            # Save the processed article in the ArticleGroq model
            ArticleGroq.objects.create(
                title=article.title,
                polarized_content=polarized_summary,
                url=article.url,
                published_at=article.published_at,
                status='processed'
            )
            success_count += 1
            logger.info(f"Successfully processed: {article.title}")

        except Exception as e:
            logger.error(f"Error processing {article.title}: {str(e)}")
            skipped_count += 1

    # Log the final counts
    logger.info(f"Processing complete. Success: {success_count}, Skipped: {skipped_count}")

    # Retrieve all entries from ArticleGroq for rendering
    processed_articles = ArticleGroq.objects.all()

    # Render the groq.html template with the processed articles
    context = {
        "articles": processed_articles,
        "success_count": success_count,
        "skipped_count": skipped_count,
    }
    return render(request, "groq.html", context)