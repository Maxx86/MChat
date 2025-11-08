import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    active_users = {}  # {room_name: set(usernames)}
    global_online = set()  # все пользователи онлайн

    async def connect(self):
        from django.contrib.auth.models import User
        from .models import Message

        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f"chat_{self.room_name}"
        self.username = (
            self.scope["user"].username if self.scope["user"].is_authenticated else "Гость"
        )

        ChatConsumer.active_users.setdefault(self.room_name, set()).add(self.username)
        ChatConsumer.global_online.add(self.username)

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.channel_layer.group_add("chat_global", self.channel_name)
        await self.accept()

        # обновляем список пользователей
        await self._update_all_user_lists()

        # загружаем историю сообщений (без блокировок)
        messages = await sync_to_async(list)(
            Message.objects.filter(room_name=self.room_name)
            .order_by("timestamp")
            .values("sender__username", "content")
        )

        for msg in messages:
            sender = msg["sender__username"] or "Гость"
            await self.send(text_data=json.dumps({
                "type": "chat",
                "message": f"{sender}: {msg['content']}"
            }))

    async def disconnect(self, close_code):
        if self.room_name in ChatConsumer.active_users:
            ChatConsumer.active_users[self.room_name].discard(self.username)

        still_online = any(
            self.username in users for users in ChatConsumer.active_users.values()
        )
        if not still_online:
            ChatConsumer.global_online.discard(self.username)

        await self._update_all_user_lists()
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        await self.channel_layer.group_discard("chat_global", self.channel_name)

    async def receive(self, text_data):
        from django.contrib.auth.models import User
        from .models import Message

        data = json.loads(text_data)
        message = data.get("message")
        if not message:
            return

        # сохраняем сообщение
        user = None
        if self.scope["user"].is_authenticated:
            user = await sync_to_async(User.objects.get)(username=self.username)

        await sync_to_async(Message.objects.create)(
            sender=user,
            content=message,
            room_name=self.room_name
        )

        # если это личка — шлём уведомление в глобальный чат
        if self.room_name.startswith("private_"):
            users = self.room_name.replace("private_", "").split("_")
            target = next((u for u in users if u != self.username), None)
            if target:
                await self.channel_layer.group_send(
                    "chat_global",
                    {
                        "type": "private_alert",
                        "sender": self.username,
                        "target": target
                    }
                )

        # отправляем сообщение в комнату
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": f"{self.username}: {message}"
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "chat",
            "message": event["message"]
        }))

    async def private_alert(self, event):
        """🔴 Сигнал для глобального чата о новом личном сообщении"""
        await self.send(text_data=json.dumps({
            "type": "private_alert",
            "sender": event["sender"],
            "target": event["target"]
        }))

    async def broadcast_user_list(self, event):
        """📡 Отправка списка всех пользователей на фронт"""
        await self.send(text_data=json.dumps({
            "type": "user_list",
            "all": event["all"],
            "online": event["online"],
        }))

    async def _update_all_user_lists(self):
        """🔄 Собирает список всех пользователей и рассылает всем"""
        from django.contrib.auth.models import User

        users_all = await sync_to_async(list)(
            User.objects.values_list("username", flat=True)
        )
        users_online = list(ChatConsumer.global_online)

        payload = {
            "type": "broadcast_user_list",  # 👈 правильный handler
            "all": users_all,
            "online": users_online
        }

        # отправляем обновление всем в глобальном и текущем чатах
        await self.channel_layer.group_send("chat_global", payload)
        await self.channel_layer.group_send(self.room_group_name, payload)
