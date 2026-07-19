from django.contrib import admin
from .models import Room, ChatUser, Message


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('code', 'created_at', 'member_count')
    search_fields = ('code',)
    readonly_fields = ('created_at',)

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'


@admin.register(ChatUser)
class ChatUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'current_room', 'created_at', 'last_seen', 'pending_cleanup_at')
    search_fields = ('username',)
    list_filter = ('current_room',)
    readonly_fields = ('created_at', 'last_seen')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'room', 'short_content', 'timestamp')
    list_filter = ('room', 'timestamp')
    search_fields = ('content', 'sender__username', 'room__code')

    def short_content(self, obj):
        return obj.content[:50]
    short_content.short_description = 'Content'