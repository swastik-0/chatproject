from django.urls import path
from . import views

urlpatterns = [

   path('chat/<str:code>/', views.chat_room, name='chat_room'),
   path('chat/<str:code>/send/', views.send_message, name='send_message'),
   path('chat/<str:code>/poll/', views.poll_messages, name='poll_messages'),
   path('cleanup/', views.cleanup_session, name='cleanup_session'),
   path('cleanup/cancel/', views.cancel_cleanup, name='cancel_cleanup'),
   path('', views.home, name='home'),
]
