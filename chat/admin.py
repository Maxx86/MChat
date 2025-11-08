from django.contrib import admin
from .models import Message

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'room_name', 'sender', 'content', 'timestamp')
    search_fields = ('room_name', 'sender__username', 'content')
    list_filter = ('room_name', 'timestamp')
