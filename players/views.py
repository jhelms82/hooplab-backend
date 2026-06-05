from rest_framework import viewsets, permissions, generics
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
from .models import Player, Session, ShotEntry
from .serializers import PlayerSerializer, SessionSerializer, ShotEntrySerializer, SignupSerializer


# NOTE: A ViewSet gives you ALL the standard doorways at once:
#   list (GET many), create (POST), retrieve (GET one), update, delete.
# You don't write each by hand — DRF builds them from the queryset + serializer.
class PlayerViewSet(viewsets.ModelViewSet):
    serializer_class = PlayerSerializer
    permission_classes = [permissions.IsAuthenticated]
    # NOTE: IsAuthenticated = you must be logged in to use these doorways.

    def get_queryset(self):
        # NOTE: only return players owned by the logged-in user — never
        # someone else's. self.request.user is whoever made the request.
        return Player.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        # NOTE: when creating a player, automatically set the owner to the
        # logged-in user (so React doesn't have to send it, and can't fake it).
        serializer.save(owner=self.request.user)


class SessionViewSet(viewsets.ModelViewSet):
    serializer_class = SessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # NOTE: only sessions belonging to THIS user's players.
        # "player__owner" follows the link: Session -> Player -> owner.
        return Session.objects.filter(player__owner=self.request.user)


class ShotEntryViewSet(viewsets.ModelViewSet):
    serializer_class = ShotEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # NOTE: only shots belonging to this user's sessions.
        # Follows the chain: ShotEntry -> Session -> Player -> owner.
        return ShotEntry.objects.filter(session__player__owner=self.request.user)

# Create your views here.


# NOTE: signup endpoint — anyone can POST here to create an account.
class SignupView(generics.CreateAPIView):
    serializer_class = SignupSerializer
    permission_classes = [permissions.AllowAny]
    # NOTE: AllowAny = no login required (you can't be logged in to sign up!).

    def create(self, request, *args, **kwargs):
        # NOTE: run the normal create (makes the user)...
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # NOTE: ...then immediately make a token so they're logged in right
        # after signing up (no separate login step needed).
        token, created = Token.objects.get_or_create(user=user)
        return Response({'token': token.key})


# ============================================================================
# PASSWORD RESET + FORGOT USERNAME
# ----------------------------------------------------------------------------
# These let a user who's locked out recover access by email. The flow:
#   1) request_password_reset  -> they enter their email; we email a reset link
#   2) confirm_password_reset  -> the link lands them on a page; they set a new pw
#   3) forgot_username         -> they enter their email; we email their username
#
# We use Django's built-in token generator (the same machinery the admin uses)
# so we don't have to invent our own secure tokens.
# ============================================================================


# NOTE: helper — checks our password rules (same as the signup form).
def password_is_valid(pw):
    if len(pw) < 8:
        return "Password must be at least 8 characters."
    if not any(c.isdigit() for c in pw):
        return "Password must include at least one number."
    return ""


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def request_password_reset(request):
    """Step 1: user submits their email; if an account exists, email a link."""
    email = request.data.get('email', '').strip()

    # NOTE: find the user by email. There could in theory be more than one
    # account with the same email, so we take the first.
    user = User.objects.filter(email__iexact=email).first()

    # NOTE: only actually send if we found someone — BUT we always return the
    # same response either way, so nobody can use this to discover which
    # emails have accounts. (Standard security practice.)
    if user:
        # NOTE: uid = the user's id, encoded; token = a secure one-time code
        # that expires and becomes invalid once the password changes.
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"

        send_mail(
            subject="Reset your PureSwish password",
            message=(
                f"Hi {user.username},\n\n"
                f"We got a request to reset your PureSwish password.\n"
                f"Click the link below to set a new one:\n\n"
                f"{reset_link}\n\n"
                f"If you didn't ask for this, you can ignore this email — "
                f"your password won't change.\n\n"
                f"— PureSwish"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

    return Response(
        {"message": "If an account exists for that email, a reset link has been sent."}
    )


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def confirm_password_reset(request):
    """Step 2: user submits uid + token + new password; we verify and update."""
    uid = request.data.get('uid', '')
    token = request.data.get('token', '')
    new_password = request.data.get('password', '')

    # NOTE: enforce the same password rules as signup.
    pw_error = password_is_valid(new_password)
    if pw_error:
        return Response({"error": pw_error}, status=400)

    # NOTE: decode the uid back into a user id and load that user.
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return Response({"error": "This reset link is invalid."}, status=400)

    # NOTE: check the token is genuine and not expired.
    if not default_token_generator.check_token(user, token):
        return Response(
            {"error": "This reset link is invalid or has expired."}, status=400
        )

    # NOTE: all good — set the new password (this also invalidates the token).
    user.set_password(new_password)
    user.save()
    return Response({"message": "Your password has been reset. You can now log in."})


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def forgot_username(request):
    """Email the user their username, looked up by email address."""
    email = request.data.get('email', '').strip()
    users = User.objects.filter(email__iexact=email)

    # NOTE: same privacy approach — always return the same message; only send
    # if we actually found account(s). If an email has multiple accounts, list them.
    if users.exists():
        usernames = "\n".join(u.username for u in users)
        send_mail(
            subject="Your PureSwish username",
            message=(
                f"Hi,\n\n"
                f"Here is the username for your PureSwish account:\n\n"
                f"{usernames}\n\n"
                f"— PureSwish"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

    return Response(
        {"message": "If an account exists for that email, the username has been sent."}
    )