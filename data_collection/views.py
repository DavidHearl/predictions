from django.shortcuts import render


def home(request):
    return render(request, 'data_collection/home.html')