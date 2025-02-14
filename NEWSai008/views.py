from django.http import HttpResponse

def homepage_view(request):
    return HttpResponse("<h1>Welcome to the NEWSai008 Project Homepage!</h1><p><a href='/broadcast/'>Go to Broadcast</a></p>")