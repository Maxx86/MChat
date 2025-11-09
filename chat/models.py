from django.db import models
from django.contrib.auth.models import User


class Message(models.Model):
    room_name = models.CharField(max_length=255)
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,   # чтобы системные сообщения не падали
        null=True,
        blank=True,
        related_name="messages"
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        sender_name = self.sender.username if self.sender else "Система"
        return f"[{self.room_name}] {sender_name}: {self.content[:30]}"
