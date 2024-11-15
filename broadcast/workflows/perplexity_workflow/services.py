from django.conf import settings
import requests
import openai
from ...models import Article

class PerplexityNewsService:
    """Service for handling Perplexity API interactions and news gathering."""
    
    @staticmethod
    def get_news_analysis(query):
        payload = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {
                    "role": "system",
                    "content": "Address the user everytime and find them two stories of opposing political views and let the user know that you're doing that. Make sure to give a source for the information from both side the republicans and the democrats. You're a reporter and take your role very seriously making sure that you're able to source all your information."
                },
                {
                    "role": "user",
                    "content": query
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
        
        response = requests.post(
            settings.PLEX_API_URL,
            headers={"Authorization": f"Bearer {settings.PLEX_API_KEY}"},
            json=payload
        )
        response.raise_for_status()
        return response.json()

class ScriptGenerationService:
    """Service for generating teleprompter scripts using OpenAI."""
    
    @staticmethod
    def generate_script(news_content):
        openai.api_key = settings.MYSK_API_KEY
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "Write a teleprompter script as official as it would be on the nightly news teleprompter and remember the anchorman name is tech with tim."
                },
                {
                    "role": "user",
                    "content": f"need this teleprompter for tech with tim:\n\n{news_content}"
                }
            ],
            max_tokens=200,
            temperature=0.7
        )
        return response['choices'][0]['message']['content'].strip()

class SpeechGenerationService:
    """Service for generating speech audio from text."""
    
    @staticmethod
    def generate_speech(text, voice="onyx"):
        payload = {
            "model": "tts-1",
            "input": text,
            "voice": voice
        }
        
        headers = {
            "Authorization": f"Bearer {settings.MYSK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.content
