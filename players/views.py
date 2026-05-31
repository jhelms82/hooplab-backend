from rest_framework import viewsets, permissions, generics
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from django.contrib.auth.models import User
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