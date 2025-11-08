from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        # Проверим, существует ли пользователь
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Пользователь с таким именем уже существует.')
            return render(request, 'registration/register.html')

        # Создаём нового пользователя
        user = User.objects.create_user(username=username, password=password)
        user.save()

        # Логиним автоматически
        login(request, user)

        # Перенаправляем в комнату (например, общую)
        return redirect('room', room_name='main')

    return render(request, 'registration/register.html')


@login_required
def room(request, room_name):
    return render(request, 'chat/room.html', {
        'room_name': room_name,
        'username': request.user.username
    })

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('room', room_name='main')
        else:
            messages.error(request, 'Неверное имя пользователя или пароль.')

    return render(request, 'registration/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')