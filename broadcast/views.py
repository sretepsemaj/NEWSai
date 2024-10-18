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
