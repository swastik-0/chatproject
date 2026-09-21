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
                # Check if the username is taken by an ACTIVE user.
                # A stale/orphaned record (pending cleanup OR not seen for >5 min)
                # is considered unclaimed — delete it and allow registration.
                existing = ChatUser.objects.filter(username__iexact=desired_username).first()
                if existing:
                    cutoff = timezone.now() - timedelta(minutes=5)
                    if existing.pending_cleanup_at is not None or existing.last_seen < cutoff:
                        # Stale user — free the username.
                        existing.delete()
                    else:
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
            # Delete the ChatUser record immediately so its username is freed at once.
            # (Relying on the 5-second cleanup grace would leave the name "taken".)
            if current_user:
                current_user.delete()
            request.session.flush()
            messages.info(request, "You now have a fresh identity.")
            return redirect('home')

        elif action == 'create_room':
            if not current_user:
                messages.error(request, "Create a profile first.")
                return redirect('home')

            code = generate_unique_room_code()
            room = Room.objects.create(code=code)
            # Assign the user to the room before redirecting so that the
            # chat_room view's guard (current_room is None → home) passes.
            current_user.current_room = room
            current_user.save(update_fields=['current_room'])
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
                messages.error(request, "Enter a valid 4-digit room code.")
                return redirect('home')

            try:
                room = Room.objects.get(code=target_code)
            except Room.DoesNotExist:
                messages.error(request, f"No room found with code {target_code}.")
                return redirect('home')

            # Assign the user to the room before redirecting so that the
            # chat_room view's guard (current_room is None → home) passes.
            current_user.current_room = room
            current_user.save(update_fields=['current_room'])
            return redirect('chat_room', code=target_code)

    return render(request, 'chat/home.html', {'current_user': current_user})


def chat_room(request, code):
    current_user = get_current_user(request)
    if not current_user:
        messages.error(request, "Create a profile first.")
        return redirect('home')

    room = get_object_or_404(Room, code=code)

    # If the user has no current_room set it means they deliberately left
    # (or were never in a room). Redirect them to home rather than
    # silently re-joining, which is what the back-button would trigger.
    if current_user.current_room_id is None:
        messages.info(request, "You left that room. Join again from the home page if you'd like to return.")
        return redirect('home')

    # If the user is already in a *different* room, redirect them to that room.
    if current_user.current_room_id != room.id:
        return redirect('chat_room', code=current_user.current_room.code)

    conversation = room.messages.order_by('timestamp')
    members = room.members.all()

    response = render(request, 'chat/chat_room.html', {
        'current_user': current_user,
        'room': room,
        'messages_list': conversation,
        'members': members,
    })
    # Prevent browser from caching this page in the bfcache so that
    # pressing Back after leaving does not restore the stale chat page.
    response['Cache-Control'] = 'no-store'
    return response


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
    # Note: last_seen uses auto_now=True, so it is updated automatically on any full save,
    # but cannot be targeted via update_fields. No extra save is needed here.

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
        # Clear the pending deletion flag AND refresh last_seen so the
        # staleness check in create_profile has an accurate heartbeat.
        # (.update() bypasses auto_now, so we set last_seen explicitly.)
        ChatUser.objects.filter(id=user_id).update(
            pending_cleanup_at=None,
            last_seen=timezone.now(),
        )
    _sweep_stale_users()
    return JsonResponse({'ok': True})