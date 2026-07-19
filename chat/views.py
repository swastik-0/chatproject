import re
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from .models import ChatUser, Room, Message
from .utils import generate_unique_username, generate_unique_room_code
from django.utils import timezone
from datetime import timedelta

CLEANUP_GRACE_SECONDS = 5
# CODE_RE = re.compile(r'^[A-Za-z0-9]{6}$')
CODE_RE = re.compile(r'^\d{4}$')

def _sweep_stale_users():
    """Lazy garbage collection: delete anyone whose cleanup mark is older
    than the grace period (meaning they closed the tab and never came back
    to cancel it). Runs opportunistically on page loads."""
    cutoff = timezone.now() - timedelta(seconds=CLEANUP_GRACE_SECONDS)
    ChatUser.objects.filter(pending_cleanup_at__isnull=False, pending_cleanup_at__lt=cutoff).delete()


def get_current_user(request):
    """Fetch the ChatUser tied to this browser session, if any."""
    _sweep_stale_users()
    user_id = request.session.get('chatuser_id')
    if not user_id:
        return None
    try:
        return ChatUser.objects.get(id=user_id)
    except ChatUser.DoesNotExist:
        del request.session['chatuser_id']
        return None

def home(request):
    current_user = get_current_user(request)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_profile':
            desired_username = request.POST.get('username', '').strip()

            if desired_username:
                if len(desired_username) > 50:
                    messages.error(request, "Username must be 50 characters or fewer.")
                    return redirect('home')
                if not re.match(r'^[A-Za-z0-9_ ]+$', desired_username):
                    messages.error(request, "Usernames can only contain letters, numbers, spaces and underscores.")
                    return redirect('home')
                if ChatUser.objects.filter(username__iexact=desired_username).exists():
                    messages.error(request, "That username is already taken. Try another, or leave it blank to auto-generate one.")
                    return redirect('home')
                username = desired_username
            else:
                username = generate_unique_username()

            new_user = ChatUser.objects.create(username=username)
            request.session['chatuser_id'] = new_user.id
            messages.success(request, f"Profile created! Welcome, {username}.")
            return redirect('home')

        elif action == 'reset_profile':
            request.session.flush()
            messages.info(request, "You now have a fresh identity.")
            return redirect('home')

        elif action == 'create_room':
            if not current_user:
                messages.error(request, "Create a profile first.")
                return redirect('home')

            code = generate_unique_room_code()
            room = Room.objects.create(code=code)
            messages.success(request, f"Room created! Share code {room.code} with others so they can join.")
            return redirect('chat_room', code=room.code)

        elif action == 'leave_room':
            if current_user:
                current_user.current_room = None
                current_user.save(update_fields=['current_room'])
            return redirect('home')
        elif action == 'join_room':
            if not current_user:
                messages.error(request, "Create a profile first.")
                return redirect('home')

            target_code = request.POST.get('target_code', '').strip().upper()
            if not CODE_RE.match(target_code):
                messages.error(request, "Enter a valid 6-character room code.")
                return redirect('home')

            if not Room.objects.filter(code=target_code).exists():
                messages.error(request, f"No room found with code {target_code}.")
                return redirect('home')

            return redirect('chat_room', code=target_code)

    return render(request, 'chat/home.html', {'current_user': current_user})


def chat_room(request, code):
    current_user = get_current_user(request)
    if not current_user:
        messages.error(request, "Create a profile first.")
        return redirect('home')

    room = get_object_or_404(Room, code=code)

    if current_user.current_room_id != room.id:
        current_user.current_room = room
        current_user.save(update_fields=['current_room'])

    conversation = room.messages.order_by('timestamp')
    members = room.members.all()

    return render(request, 'chat/chat_room.html', {
        'current_user': current_user,
        'room': room,
        'messages_list': conversation,
        'members': members,
    })


@require_POST
def send_message(request, code):
    current_user = get_current_user(request)
    if not current_user:
        return JsonResponse({'error': 'No active profile.'}, status=403)

    room = get_object_or_404(Room, code=code.upper())

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return HttpResponseBadRequest("Invalid request body.")

    content = (payload.get('content') or '').strip()
    if not content:
        return JsonResponse({'error': 'Message cannot be empty.'}, status=400)
    if len(content) > 2000:
        return JsonResponse({'error': 'Message too long (max 2000 characters).'}, status=400)

    msg = Message.objects.create(room=room, sender=current_user, content=content)
    current_user.save(update_fields=['last_seen'])

    return JsonResponse({
        'id': msg.id,
        'sender_username': current_user.username,
        'content': msg.content,
        'timestamp': msg.timestamp.isoformat(),
        'is_self': True,
    })


@require_GET
def poll_messages(request, code):
    current_user = get_current_user(request)
    if not current_user:
        return JsonResponse({'error': 'No active profile.'}, status=403)

    room = get_object_or_404(Room, code=code.upper())

    after_id = request.GET.get('after', 0)
    try:
        after_id = int(after_id)
    except ValueError:
        after_id = 0

    conversation = Message.objects.filter(room=room, id__gt=after_id).select_related('sender').order_by('timestamp')

    data = [{
        'id': m.id,
        'sender_username': m.sender.username,
        'content': m.content,
        'timestamp': m.timestamp.isoformat(),
        'is_self': m.sender_id == current_user.id,
    } for m in conversation]
    member_names = list(room.members.values_list('username', flat=True))
    return JsonResponse({'messages': data, 'members': member_names})
    # return JsonResponse({'messages': data})



@csrf_exempt
def cleanup_session(request):
    """Called via sendBeacon when the page unloads. Doesn't delete
    immediately — just marks the user for deletion. A refresh will
    cancel this mark before the grace period runs out."""
    user_id = request.session.get('chatuser_id')
    if user_id:
        ChatUser.objects.filter(id=user_id).update(pending_cleanup_at=timezone.now())
    return JsonResponse({'ok': True})


@csrf_exempt
def cancel_cleanup(request):
    user_id = request.session.get('chatuser_id')
    if user_id:
        ChatUser.objects.filter(id=user_id).update(pending_cleanup_at=None)
    _sweep_stale_users()
    return JsonResponse({'ok': True})