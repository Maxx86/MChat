from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from chat import views as chat_views


def home(request):
    return HttpResponse("<h1>👋 Добро пожаловать в MChat!</h1><p>Перейди в <a href='/chat/'>чат</a></p>")


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', chat_views.register, name='register'),  # главная страница — регистрация
    path('chat/', include('chat.urls')),             # комната по /chat/room_name/
]