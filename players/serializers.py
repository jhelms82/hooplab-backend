from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Player, Session, ShotEntry


# NOTE: translates ShotEntry rows <-> JSON
class ShotEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = ShotEntry
        fields = ['id', 'session', 'spot', 'makes', 'attempts']

# NOTE: translates Session rows <-> JSON.
# It also NESTS the session's shots inside it, so one request gives you
# the session AND all its shot entries together.
class SessionSerializer(serializers.ModelSerializer):
    shots = ShotEntrySerializer(many=True, read_only=True)

    class Meta:
        model = Session
        fields = ['id', 'player', 'date', 'focus', 'created_at', 'shots']


# NOTE: translates Player rows <-> JSON
class PlayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = ['id', 'owner', 'name', 'number', 'created_at']
        # NOTE: owner is set automatically by the view (to the logged-in user),
        # so it must NOT be required in incoming data — read_only fixes that.
        read_only_fields = ['owner']


# NOTE: handles creating a new user account from signup data.
class SignupSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']
        extra_kwargs = {
            'password': {'write_only': True},
            # NOTE: email is now REQUIRED — an account needs an email so the
            # user can reset their password / recover their username later.
            'email': {'required': True, 'allow_blank': False},
        }

    # NOTE: runs before saving — rejects a username that already exists.
    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is already taken.")
        return value

    # NOTE: enforce ONE ACCOUNT PER EMAIL. iexact = case-insensitive, so
    # "John@x.com" and "john@x.com" are treated as the same email.
    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with that email already exists.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )
        return user