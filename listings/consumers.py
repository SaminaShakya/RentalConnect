import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Booking, BookingMessage

User = get_user_model()


class BookingMessageConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.booking_id = self.scope['url_route']['kwargs']['booking_id']
        self.room_group_name = f'booking_{self.booking_id}'

        # Check if user has permission to access this booking
        if await self.can_access_booking():
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'send_message':
            await self.handle_send_message(data)

    async def handle_send_message(self, data):
        content = data.get('content', '').strip()
        if not content:
            return

        user = self.scope['user']
        if not user.is_authenticated:
            return

        # Save message to database
        message = await self.save_message(user, content)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id': message.id,
                    'sender': user.username,
                    'content': content,
                    'created_at': message.created_at.isoformat(),
                    'is_read': message.is_read,
                }
            }
        )

    async def chat_message(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': message
        }))

    @database_sync_to_async
    def can_access_booking(self):
        try:
            user = self.scope['user']
            if not user.is_authenticated:
                return False

            booking = Booking.objects.get(id=self.booking_id)
            return booking.tenant == user or booking.property.landlord == user
        except Booking.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, user, content):
        booking = Booking.objects.get(id=self.booking_id)
        return BookingMessage.objects.create(
            booking=booking,
            sender=user,
            content=content
        )