from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages


def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if not username or not password:
            messages.error(request, 'Пожалуйста, заполните все поля')
            return render(request, 'registration/register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Такой пользователь уже существует')
            return render(request, 'registration/register.html')

        user = User.objects.create_user(username=username, password=password)
        login(request, user)
        return redirect('global_chat')

    return render(request, 'registration/register.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('global_chat')
        else:
            messages.error(request, 'Неверный логин или пароль')

    return render(request, 'registration/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def global_chat(request):
    return render(request, "chat/room.html", {
        "room_name": "global",
        "username": request.user.username,
    })


@login_required
def private_chat(request, username):
    me = request.user.username
    a, b = sorted([me, username])
    room_name = f"private_{a}_{b}"
    return render(request, "chat/room.html", {
        "room_name": room_name,
        "username": me,
    })


@login_required
def room(request, room_name):
    return render(request, "chat/room.html", {
        "room_name": room_name,
        "username": request.user.username,
    })
