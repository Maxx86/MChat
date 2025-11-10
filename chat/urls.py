from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('global/', views.global_chat, name='global_chat'),
    path('private/<str:username>/', views.private_chat, name='private_chat'),
    path('<str:room_name>/', views.room, name='room'),
]
