from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .services import PerplexityNewsService, ScriptGenerationService, SpeechGenerationService, GroqNewsProcessor
import json
import logging
import os

logger = logging.getLogger(__name__)

@csrf_exempt
def reporter_view(request):
    """View for getting news analysis from Perplexity and processing with Groq."""
    if request.method == 'POST':
        try:
            # Check if this is an AJAX request for processing
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.headers.get('Content-Type') == 'application/json':
                try:
                    data = json.loads(request.body)
                    if data.get('action') == 'process_story':
                        raw_story = request.session.get('raw_news_story', '')
                        if not raw_story:
                            return JsonResponse({'error': 'No raw story found to process'}, status=400)
                        
                        try:
                            # Process the story using Groq
                            processed_story = GroqNewsProcessor.process_news(raw_story)
                            
                            # Save to session
                            request.session['news_story'] = processed_story
                            request.session.modified = True
                            
                            return JsonResponse({
                                'success': True,
                                'processed_story': processed_story
                            })
                        except Exception as process_error:
                            logger.error(f"Story processing error: {str(process_error)}")
                            return JsonResponse(
                                {'error': f"Failed to process story: {str(process_error)}"}, 
                                status=500
                            )
                except json.JSONDecodeError:
                    return JsonResponse({'error': 'Invalid JSON request'}, status=400)
            else:
                # Handle regular form submission (generate raw story)
                user_query = request.POST.get('query', '').strip()
                if not user_query:
                    return render(request, 'broadcast/reporter.html', 
                                {'error': 'Please enter a query.'})

                try:
                    # Get news analysis from Perplexity
                    news_service = PerplexityNewsService()
                    api_data = news_service.get_news_analysis(user_query)
                    
                    # Extract raw story from API response
                    raw_story = api_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    if not raw_story:
                        return render(request, 'broadcast/reporter.html', 
                                    {'error': 'No story found. Please try a different query.'})
                    
                    # Save raw story to session
                    request.session['raw_news_story'] = raw_story
                    request.session['news_story'] = ''
                    request.session.modified = True
                    
                    return render(request, 'broadcast/reporter.html', {
                        'raw_story': raw_story,
                        'show_process_button': True
                    })
                except Exception as story_error:
                    logger.error(f"Raw story generation error: {str(story_error)}")
                    return render(request, 'broadcast/reporter.html', 
                                {'error': f"Failed to generate story: {str(story_error)}"})
            
        except Exception as e:
            logger.error(f"Error in reporter view: {str(e)}")
            return render(request, 'broadcast/reporter.html', {'error': str(e)})
    
    # GET request - show raw story from session
    raw_story = request.session.get('raw_news_story', '')
    return render(request, 'broadcast/reporter.html', {
        'raw_story': raw_story,
        'show_process_button': bool(raw_story)
    })

def director_view(request):
    """View for generating teleprompter script."""
    reporter_response = request.session.get('news_story', '')
    raw_story = request.session.get('raw_news_story', '')

    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            if data.get('action') == 'generate_script':
                if not reporter_response:
                    return JsonResponse(
                        {'error': 'No processed story available. Please generate a story from the Reporter page first.'}, 
                        status=400
                    )

                try:
                    # Generate script using both processed and raw stories for context
                    script_service = ScriptGenerationService()
                    context = f"""PROCESSED STORY:
{reporter_response}

ORIGINAL SOURCES:
{raw_story}"""
                    teleprompter_script = script_service.generate_script(context)
                    
                    # Save to session
                    request.session['teleprompter_script'] = teleprompter_script
                    request.session['original_script'] = teleprompter_script  # Save original for reference
                    
                    return JsonResponse({'teleprompter_script': teleprompter_script})
                except Exception as script_error:
                    logger.error(f"Script generation error: {str(script_error)}")
                    return JsonResponse(
                        {'error': f"Failed to generate script: {str(script_error)}"}, 
                        status=500
                    )
            
            return JsonResponse({'error': 'Invalid action'}, status=400)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON request'}, status=400)
        except Exception as e:
            logger.error(f"Error in director view: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    teleprompter_script = request.session.get('teleprompter_script', '')
    original_script = request.session.get('original_script', '')
    
    return render(request, 'broadcast/director.html', {
        'reporter_response': reporter_response,
        'raw_story': raw_story,
        'teleprompter_script': teleprompter_script,
        'original_script': original_script,
        'has_story': bool(reporter_response)
    })

@csrf_exempt
def anchorman_view(request):
    """View for generating speech from script."""
    if request.method == 'POST':
        try:
            # Check if this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                try:
                    data = json.loads(request.body)
                    script = data.get('script', '')
                    
                    if not script:
                        return JsonResponse({'error': 'No script provided'}, status=400)
                    
                    # Generate speech
                    speech_service = SpeechGenerationService()
                    relative_path = speech_service.generate_speech(script)
                    
                    # Construct the full URL
                    mp3_url = request.build_absolute_uri(settings.MEDIA_URL + relative_path)
                    
                    return JsonResponse({
                        'status': 'success',
                        'message': 'Speech generated successfully',
                        'mp3_url': mp3_url
                    })
                    
                except json.JSONDecodeError:
                    return JsonResponse({'error': 'Invalid JSON request'}, status=400)
                except Exception as e:
                    logger.error(f"Error generating speech: {str(e)}")
                    return JsonResponse({'error': str(e)}, status=500)
            else:
                return JsonResponse({'error': 'Invalid request'}, status=400)
                
        except Exception as e:
            logger.error(f"Error in anchorman view: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    # GET request
    script = request.session.get('teleprompter_script', '')
    return render(request, 'broadcast/anchorman.html', {
        'script': script,
        'has_script': bool(script)
    })
