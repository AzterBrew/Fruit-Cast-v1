from django.shortcuts import render
from django.http import HttpResponse

# def Homepage(request):
#     # return HttpResponse("Hello po. This is home")
#     return render(request, 'home.html')

def About(request):
    # return HttpResponse("About page")
    return render(request, 'about.html')

