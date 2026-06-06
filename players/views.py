from rest_framework import viewsets, permissions, generics
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
import resend
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
# These let a user who's locked out recover access by email.
#
# IMPORTANT: We send email via Resend's HTTP API (not SMTP). Render's free tier
# blocks outbound SMTP ports, so Django's send_mail() hangs forever there.
# Resend sends over HTTPS (port 443), which works fine on Render.
# ============================================================================


# NOTE: small helper that actually sends an email through Resend.
# Reads the API key + "from" address from settings (which read env vars).
def send_email(to_address, subject, body):
    resend.api_key = settings.RESEND_API_KEY
    resend.Emails.send({
        "from": settings.RESEND_FROM_EMAIL,
        "to": [to_address],
        "subject": subject,
        "text": body,
    })


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

        send_email(
            to_address=email,
            subject="Reset your PureSwish password",
            body=(
                f"Hi {user.username},\n\n"
                f"We got a request to reset your PureSwish password.\n"
                f"Click the link below to set a new one:\n\n"
                f"{reset_link}\n\n"
                f"If you didn't ask for this, you can ignore this email — "
                f"your password won't change.\n\n"
                f"— PureSwish"
            ),
        )

    return Response(
        {"message": "If an account exists for that email, a reset link has been sent."}
    )


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def request_password_reset(request):
    """TEMPORARY DIAGNOSTIC — revert after. Reveals exactly what's happening."""
    email = request.data.get('email', '').strip()
    user = User.objects.filter(email__iexact=email).first()

    debug = {
        "email_received": email,
        "user_found": bool(user),
        "username": user.username if user else None,
        "key_set": bool(settings.RESEND_API_KEY),
        "from_email": settings.RESEND_FROM_EMAIL,
        "frontend_url": settings.FRONTEND_URL,
    }

    if user:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
        try:
            result = send_email(
                to_address=email,
                subject="Reset your PureSwish password",
                body=f"Reset your password:\n\n{reset_link}\n\n— PureSwish",
            )
            debug["send_result"] = str(result)
        except Exception as e:
            debug["send_error"] = repr(e)

    return Response(debug)

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
        send_email(
            to_address=email,
            subject="Your PureSwish username",
            body=(
                f"Hi,\n\n"
                f"Here is the username for your PureSwish account:\n\n"
                f"{usernames}\n\n"
                f"— PureSwish"
            ),
        )

    return Response(
        {"message": "If an account exists for that email, the username has been sent."}
    )