from django.db import models


class Room(models.Model):
    code = models.CharField(max_length=4, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Room {self.code}"


class ChatUser(models.Model):
    """A guest chat identity. No password / account system - just a
    username. Users join a shared Room using its 4-digit code."""
    username = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    current_room = models.ForeignKey('Room', null=True, blank=True, on_delete=models.SET_NULL, related_name='members')
    pending_cleanup_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Chat User"
        verbose_name_plural = "Chat Users"

    def __str__(self):
        return self.username


class Message(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(ChatUser, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField(max_length=2000)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        preview = self.content[:30]
        return f"{self.sender.username} in {self.room.code}: {preview}"