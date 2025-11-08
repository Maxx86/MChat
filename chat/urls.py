from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('<str:room_name>/', views.room, name='room'),  # должен идти в самом конце!
]
