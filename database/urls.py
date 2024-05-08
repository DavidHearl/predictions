from django.urls import path
from django.shortcuts import render, HttpResponse, redirect, get_object_or_404
from . import views

urlpatterns = [
    path('', views.index, name='index'),
]