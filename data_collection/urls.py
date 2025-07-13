from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('players/', views.players, name='players'),
    path('players/<int:pk>/', views.player_detail, name='player_detail'),
    path('players/<int:pk>/edit/', views.player_edit, name='player_edit'),
    path('matches/', views.matches, name='matches'),
    path('matches/<int:pk>/', views.match_detail, name='match_detail'),
    path('shots/', views.shots, name='shots'),
    path('teams/', views.teams, name='teams'),
    path('teams/<int:pk>/', views.team_detail, name='team_detail'),
]