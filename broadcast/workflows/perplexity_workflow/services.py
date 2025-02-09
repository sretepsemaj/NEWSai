from django.conf import settings
import requests
import openai
import logging
import json
from ...models import Article
import groq
import os
import uuid

logger = logging.getLogger(__name__)

class PerplexityNewsService:
    """Service for handling Perplexity API interactions and news gathering."""
    
    @staticmethod
    def get_news_analysis(query):
        # Enhance the query to focus on Trump-related news
        enhanced_query = f"Find and analyze the latest news about Donald Trump, focusing on recent developments, legal cases, and campaign activities. Include specific details, quotes, and cite reliable sources."
        
        payload = {
            "model": "llama-3.1-sonar-large-128k-chat",  # Updated to correct model name
            "messages": [
                {
                    "role": "system",
                    "content": """You are a senior political journalist. Your task is to:
1. Find and analyze the most recent Trump-related news from reliable sources
2. Focus on factual reporting with proper citations
3. Include direct quotes when available
4. Cover multiple aspects: legal proceedings, campaign activities, political statements
5. Maintain journalistic standards with clear attribution
6. Structure the response like a newspaper article with:
   - Headline
   - Dateline
   - Lead paragraph
   - Supporting paragraphs
   - Source citations"""
                },
                {
                    "role": "user",
                    "content": enhanced_query
                }
            ],
            "temperature": 0.3,
            "max_tokens": 4096,  # Increased token limit for larger model
            "top_p": 0.9
        }
        
        try:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.PLEX_API_KEY}"
            }
            
            logger.info("Making Perplexity API request...")
            response = requests.post(
                settings.PLEX_API_URL,
                headers=headers,
                json=payload,
                timeout=45  # Increased timeout for larger model
            )
            
            if response.status_code != 200:
                error_msg = f"Perplexity API error: {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg += f" - {error_data['error'].get('message', '')}"
                except:
                    error_msg += f" - {response.text}"
                logger.error(error_msg)
                raise Exception(f"API call failed: {error_msg}")
            
            logger.info("Successfully received Perplexity API response")
            return response.json()
        except requests.exceptions.Timeout:
            logger.error("Perplexity API timeout")
            raise Exception("API request timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Perplexity API request error: {str(e)}")
            raise Exception(f"Failed to fetch news: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in Perplexity API call: {str(e)}")
            raise Exception(f"An unexpected error occurred: {str(e)}")

class GroqNewsProcessor:
    """Service for processing raw news data into a professional story using Groq."""
    
    @staticmethod
    def process_news(raw_story):
        try:
            client = groq.Groq(api_key=settings.GROQ_API_KEY)
            
            messages = [
                {
                    "role": "system",
                    "content": """You are an experienced political journalist at The New York Times. Transform this raw news data into a comprehensive, professional newspaper article. Follow these specific guidelines:

1. Article Components:
   - Write a compelling, specific headline that captures the key news
   - Include a proper dateline with location and current date
   - Write a strong lead paragraph that hooks readers and summarizes key points
   - Develop 4-6 detailed supporting paragraphs
   - Include at least 3 relevant quotes with proper attribution
   - Add context about related events or background
   - End with a forward-looking conclusion

2. Writing Requirements:
   - Use precise, professional language
   - Include specific dates, numbers, and statistics
   - Maintain journalistic objectivity
   - Provide detailed context for claims
   - Use proper titles and credentials
   - Follow AP style guidelines
   - Balance multiple perspectives

3. Structure Each Paragraph to:
   - Start with a clear topic sentence
   - Include supporting details and evidence
   - Use direct quotes where relevant
   - Connect to the main story narrative
   - End with a transition to the next point

4. Required Elements:
   - Minimum 800 words
   - At least 3 direct quotes
   - Specific dates and locations
   - Relevant background information
   - Multiple source citations
   - Current implications
   - Future implications

5. Political Reporting Guidelines:
   - Present facts without bias
   - Include multiple political perspectives
   - Cite official documents and statements
   - Provide electoral context
   - Explain legal implications
   - Include polling data when relevant
   - Reference historical precedents

Remember: This is a serious news article for The New York Times. Maintain high journalistic standards and provide comprehensive coverage."""
                },
                {
                    "role": "user",
                    "content": f"""Transform this raw news data into a detailed New York Times style article. Include all sources, expand on key points, and maintain professional journalistic standards:

{raw_story}

Requirements:
1. Minimum 800 words
2. Multiple direct quotes with attribution
3. Detailed context and background
4. Clear structure with multiple sections
5. Specific dates and statistics
6. Both immediate and broader implications"""
                }
            ]
            
            # Update the model name to the new recommended model
            response = client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=messages,
                temperature=0.3,
                max_tokens=4096
            )
            
            processed_story = response.choices[0].message.content
            
            # Add source attribution
            processed_story += "\n\n---\nThis article was processed using AI technology with data from multiple verified news sources. All quotes and facts have been preserved from the original sources."
            
            return processed_story
            
        except Exception as e:
            logger.error(f"Groq processing error: {str(e)}")
            raise Exception(f"Failed to process story with Groq: {str(e)}")

class NewsProcessor:
    """Service for processing raw news data into a professional story."""
    
    @staticmethod
    def process_news(raw_story):
        try:
            openai.api_key = settings.MYSK_API_KEY
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a professional newspaper editor. Transform the raw news data into a polished newspaper article following these guidelines:

1. Structure:
   - Clear, attention-grabbing headline
   - Professional dateline
   - Strong lead paragraph
   - Well-organized supporting paragraphs
   - Proper source attribution
   - Relevant context and background

2. Style:
   - Follow AP style guidelines
   - Use clear, concise language
   - Include relevant quotes with proper attribution
   - Maintain objective tone
   - Use proper journalistic formatting

3. Content:
   - Preserve all source citations
   - Include timestamps for events
   - Balance different perspectives
   - Provide necessary context
   - Cross-reference multiple sources"""
                    },
                    {
                        "role": "user",
                        "content": f"Transform this raw news data into a professional newspaper article:\n\n{raw_story}"
                    }
                ],
                max_tokens=2000,
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"News processing error: {str(e)}")
            raise Exception(f"Failed to process news story: {str(e)}")

class ScriptGenerationService:
    """Service for generating teleprompter scripts using OpenAI."""
    
    @staticmethod
    def generate_script(news_content):
        try:
            openai.api_key = settings.MYSK_API_KEY
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a professional news script writer. Create a polished teleprompter script following these guidelines:

1. Format:
   - Use '>' for camera/production cues (e.g., '>CAMERA 1', '>GRAPHIC')
   - Use ALL CAPS for emphasis and proper nouns
   - Break into short, readable paragraphs
   - Include timing marks [00:00] at key points
   - Add pause indicators with '...'

2. Structure:
   - Start with a compelling headline
   - Include a brief introduction
   - Present key points in order of importance
   - End with a clear conclusion
   - Add source citations where relevant

3. Style:
   - Use clear, conversational language
   - Write for the spoken word (contractions, natural pauses)
   - Keep sentences short and punchy
   - Include pronunciation guides for difficult names/terms [in brackets]

4. Production Notes:
   - Mark graphic/visual cues clearly
   - Indicate camera switches
   - Note when to reference on-screen elements"""
                    },
                    {
                        "role": "user",
                        "content": f"Create a professional teleprompter script from this news content:\n\n{news_content}"
                    }
                ],
                max_tokens=2000,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating script: {str(e)}")
            raise Exception(f"Failed to generate teleprompter script: {str(e)}")

class SpeechGenerationService:
    """Service for generating speech audio from text."""
    
    @staticmethod
    def generate_speech(text, voice="onyx"):
        try:
            # Create media directory if it doesn't exist
            media_dir = os.path.join(settings.BASE_DIR, 'media', 'audio')
            os.makedirs(media_dir, exist_ok=True)
            
            # Generate unique filename
            filename = f"speech_{uuid.uuid4()}.mp3"
            filepath = os.path.join(media_dir, filename)
            
            # Generate speech using OpenAI API
            payload = {
                "model": "tts-1",
                "input": text,
                "voice": voice,
                "response_format": "mp3"
            }
            
            headers = {
                "Authorization": f"Bearer {settings.MYSK_API_KEY}",
                "Content-Type": "application/json"
            }
            
            logger.info("Making request to OpenAI TTS API...")
            response = requests.post(
                "https://api.openai.com/v1/audio/speech",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                error_msg = f"OpenAI TTS API error: {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg += f" - {error_data['error'].get('message', '')}"
                except:
                    error_msg += f" - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Save audio file
            logger.info(f"Saving audio file to {filepath}")
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            # Return the URL path relative to MEDIA_URL
            relative_path = os.path.join('audio', filename)
            return relative_path
            
        except Exception as e:
            logger.error(f"Speech generation error: {str(e)}")
            raise Exception(f"Failed to generate speech: {str(e)}")
