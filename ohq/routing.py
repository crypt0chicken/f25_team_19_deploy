from django.urls import path
from ohq import consumers

websocket_urlpatterns = [
    path('ohq/data/queue/<int:id>', consumers.QueueConsumer.as_asgi()),
    path('ohq/data/queue-list', consumers.QueueListConsumer.as_asgi()),
]