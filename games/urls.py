from django.urls import path
from . import views

app_name = 'games'

urlpatterns = [
    path('<slug:slug>/', views.GamePageView.as_view(), name='game_play'),
    path('<slug:slug>/submit/', views.GameSubmitView.as_view(), name='game_submit'),
]
