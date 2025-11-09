# chat/consumers.py
import json
from datetime import timedelta

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone
from django.utils.text import slugify


class ChatConsumer(AsyncWebsocketConsumer):
    active_users = {}
    global_online = set()

    # ---------- helpers ----------

    async def _get_system_user(self):
        """Создаёт/возвращает пользователя System для системных сообщений."""
        from django.contrib.auth.models import User

        def _get_or_create():
            u, created = User.objects.get_or_create(username="System")
            if created:
                u.set_unusable_password()
                u.save()
            return u

        return await sync_to_async(_get_or_create)()

    @staticmethod
    def _fmt(ts):
        """Локализуем timestamp и показываем как [ДД.ММ, ЧЧ:ММ]."""
        local = timezone.localtime(ts)
        return local.strftime("%d.%m, %H:%M")

    # ---------- ws lifecycle ----------

    async def connect(self):
        from django.contrib.auth.models import User  # noqa
        from .models import Message

        raw_room_name = self.scope["url_route"]["kwargs"]["room_name"]
        safe_room = slugify(raw_room_name)
        self.room_name = raw_room_name
        self.room_group_name = f"chat_{safe_room}"

        self.username = (
            self.scope["user"].username if self.scope["user"].is_authenticated else "Гость"
        )

        ChatConsumer.active_users.setdefault(self.room_name, set()).add(self.username)
        ChatConsumer.global_online.add(self.username)

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.channel_layer.group_add("chat_global", self.channel_name)
        await self.accept()

        # системный лог входа в общий чат (без дублей в пределах 2 минут)
        if self.room_name == "global":
            system_user = await self._get_system_user()
            content = f"🔵 {self.username} вошёл(а) в чат"

            recent_exists = await sync_to_async(
                Message.objects.filter(
                    sender=system_user,
                    content=content,
                    timestamp__gte=timezone.now() - timedelta(minutes=2),
                    room_name="global",
                ).exists
            )()

            if not recent_exists:
                msg = await sync_to_async(Message.objects.create)(
                    sender=system_user,
                    content=content,
                    room_name="global",
                )
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "chat_message",
                        "message": f"[{self._fmt(msg.timestamp)}] System: {msg.content}",
                    },
                )

        # обновляем списки онлайна
        await self._update_all_user_lists()

        # история комнаты (время берём из БД, форматируем локально)
        messages = await sync_to_async(list)(
            Message.objects.filter(room_name=self.room_name)
            .order_by("timestamp")
            .values("sender__username", "content", "timestamp")
        )
        for m in messages:
            sender = m["sender__username"] or "System"
            ts = self._fmt(m["timestamp"])
            await self.send(
                text_data=json.dumps(
                    {"type": "chat", "message": f"[{ts}] {sender}: {m['content']}"}
                )
            )

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

    # ---------- messages ----------

    async def receive(self, text_data):
        from django.contrib.auth.models import User
        from .models import Message

        data = json.loads(text_data)
        message = data.get("message")
        if not message:
            return

        user = None
        if self.scope["user"].is_authenticated:
            user = await sync_to_async(User.objects.get)(username=self.username)

        msg = await sync_to_async(Message.objects.create)(
            sender=user,
            content=message,
            room_name=self.room_name,
        )

        formatted = f"[{self._fmt(msg.timestamp)}] {self.username}: {message}"

        # алерт в глобал при личке
        if self.room_name.startswith("private_"):
            users = self.room_name.replace("private_", "").split("_")
            target = next((u for u in users if u != self.username), None)
            if target:
                await self.channel_layer.group_send(
                    "chat_global",
                    {"type": "private_alert", "sender": self.username, "target": target},
                )

        await self.channel_layer.group_send(
            self.room_group_name, {"type": "chat_message", "message": formatted}
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({"type": "chat", "message": event["message"]}))

    async def private_alert(self, event):
        await self.send(
            text_data=json.dumps(
                {"type": "private_alert", "sender": event["sender"], "target": event["target"]}
            )
        )

    async def broadcast_user_list(self, event):
        await self.send(
            text_data=json.dumps({"type": "user_list", "all": event["all"], "online": event["online"]})
        )

    # ---------- users list ----------

    async def _update_all_user_lists(self):
        from django.contrib.auth.models import User

        users_all = await sync_to_async(list)(User.objects.values_list("username", flat=True))
        users_online = list(ChatConsumer.global_online)

        payload = {"type": "broadcast_user_list", "all": users_all, "online": users_online}
        await self.channel_layer.group_send("chat_global", payload)
        await self.channel_layer.group_send(self.room_group_name, payload)
