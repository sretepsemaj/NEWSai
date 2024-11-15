from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services import PerplexityNewsService, ScriptGenerationService, SpeechGenerationService
import json
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
def reporter_view(request):
    """View for getting news analysis from Perplexity."""
    if request.method == 'POST':
        try:
            user_query = request.POST.get('query', '')
            if not user_query:
                return render(request, 'broadcast/reporter.html', 
                            {'error': 'Please enter a query.'})

            # Get news analysis from Perplexity
            news_service = PerplexityNewsService()
            api_data = news_service.get_news_analysis(user_query)
            
            # Extract story from API response
            story = api_data.get('choices', [{}])[0].get('message', {}).get('content', 
                                                                          'No story found.')
            
            # Save to session
            request.session['news_story'] = story
            
            return render(request, 'broadcast/reporter.html', {'story': story})
            
        except Exception as e:
            logger.error(f"Error in reporter view: {str(e)}")
            return render(request, 'broadcast/reporter.html', {'error': str(e)})
    
    # GET request
    story = request.session.get('news_story', '')
    return render(request, 'broadcast/reporter.html', {'story': story})

def director_view(request):
    """View for generating teleprompter script."""
    reporter_response = request.session.get('news_story', 'No data available')

    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            if data.get('action') == 'generate_script':
                if not reporter_response:
                    return JsonResponse(
                        {'error': 'No data available from reporter'}, 
                        status=400
                    )

                # Generate script
                script_service = ScriptGenerationService()
                teleprompter_script = script_service.generate_script(reporter_response)
                
                # Save to session
                request.session['teleprompter_script'] = teleprompter_script
                
                return JsonResponse({'teleprompter_script': teleprompter_script})
            
            return JsonResponse({'error': 'Invalid action'}, status=400)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Error in director view: {str(e)}")
            return JsonResponse({'error': f"API call failed: {str(e)}"}, status=500)

    teleprompter_script = request.session.get('teleprompter_script', 
                                            'No teleprompter script available')
    
    return render(request, 'broadcast/director.html', {
        'reporter_response': reporter_response,
        'teleprompter_script': teleprompter_script,
    })

def anchorman_view(request):
    """View for generating speech from script."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            script = data.get('script', '')
            
            if not script:
                return JsonResponse({'error': 'No script provided'}, status=400)
            
            # Generate speech
            speech_service = SpeechGenerationService()
            audio_content = speech_service.generate_speech(script)
            
            # Here you would typically save the audio file and return its URL
            # For now, we'll just return success
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            logger.error(f"Error in anchorman view: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    script = request.session.get('teleprompter_script', '')
    return render(request, 'broadcast/anchorman.html', {'script': script})
