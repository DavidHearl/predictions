from django.shortcuts import render, HttpResponse, redirect, get_object_or_404
from django.http import HttpResponseRedirect


def index(request):
    return render(request, 'overall_statistics.html')
