import random
import string

from .models import ChatUser, Room

ADJECTIVES = [
    "Swift", "Quiet", "Brave", "Lucky", "Calm", "Bright", "Clever", "Bold",
    "Gentle", "Mighty", "Silent", "Cosmic", "Golden", "Silver", "Rapid",
    "Mystic", "Sunny", "Frosty", "Electric", "Wandering",
]

NOUNS = [
    "Fox", "Falcon", "Tiger", "Panda", "Otter", "Eagle", "Wolf", "Dolphin",
    "Comet", "Phoenix", "Raven", "Lynx", "Panther", "Sparrow", "Maverick",
    "Nomad", "Voyager", "Pioneer", "Rocket", "Wizard",
]

# Excludes visually-confusable characters (0/O, 1/I) so codes are easy
# to read aloud or copy over a call.
ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_unique_username():
    """Generate a fun random username like 'SwiftFox482' that isn't taken."""
    for _ in range(100):
        candidate = f"{random.choice(ADJECTIVES)}{random.choice(NOUNS)}{random.randint(10, 999)}"
        if not ChatUser.objects.filter(username=candidate).exists():
            return candidate
    # Extremely unlikely fallback
    return f"Guest{random.randint(100000, 999999)}"


# def generate_unique_room_code():
#     """Generate a unique 6-character room code (e.g. 'K7QX2P').

#     This is the single code that any number of people can use to join
#     the same room - it identifies a *room*, not a person, so it can be
#     shared with a whole group instead of being exchanged one-to-one.
#     """
#     for _ in range(1000):
#         candidate = ''.join(random.choice(ROOM_CODE_ALPHABET) for _ in range(6))
#         if not Room.objects.filter(code=candidate).exists():
#             return candidate
#     raise RuntimeError("Could not generate a unique room code. Try again.")

# in 4 digit pin type
def generate_unique_room_code():
    """Generate a unique 4-digit numeric room code (e.g. '0472')."""
    for _ in range(1000):
        candidate = f"{random.randint(0, 9999):04d}"
        if not Room.objects.filter(code=candidate).exists():
            return candidate
    raise RuntimeError("No available 4-digit codes left. Capacity reached (10,000 rooms).")