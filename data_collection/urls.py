from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('players/', views.players, name='players'),
    path('players/<int:pk>/', views.player_detail, name='player_detail'),
    path('players/<int:pk>/edit/', views.player_edit, name='player_edit'),
]