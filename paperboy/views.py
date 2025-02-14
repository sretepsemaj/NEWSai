from django.shortcuts import render
from django.http import JsonResponse

def paperboy_view(request):
    mp3_url = request.session.get('mp3_url')
    headline = None

    if mp3_url:
        # Simulate sending the MP3 to an external service to generate a headline
        headline = "AI-generated headline: Breaking News!"
        request.session['headline'] = headline  # Save headline to session

    return render(request, 'paperboy/index.html', {'mp3_url': mp3_url, 'headline': headline})
