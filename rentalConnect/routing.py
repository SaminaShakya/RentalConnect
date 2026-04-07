from django.urls import re_path
from listings.consumers import BookingMessageConsumer

websocket_urlpatterns = [
    re_path(r'ws/booking/(?P<booking_id>\d+)/messages/$', BookingMessageConsumer.as_asgi()),
]