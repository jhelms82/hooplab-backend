from django.db import models

# Create your models here.

class Player(models.Model):
    # NOTE: who owns this player record (the parent/coach who logged in).
    # This links each Player to a User — like a foreign key in SQL.
    owner = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='players'
    )
    # NOTE: the player's name
    name = models.CharField(max_length=100)
    # NOTE: jersey number — optional, so blank/null allowed
    number = models.IntegerField(blank=True, null=True)
    # NOTE: when this record was created (set automatically)
    created_at = models.DateTimeField(auto_now_add=True)

    # NOTE: what shows in the admin list instead of "Player object (1)"
    def __str__(self):
        return self.name


class Session(models.Model):
    # NOTE: which player this workout belongs to.
    # Links each Session to a Player — foreign key, like in SQL.
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    # NOTE: the date of the workout
    date = models.DateField()
    # NOTE: optional notes / focus areas, stored as text
    focus = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.player.name} — {self.date}"


class ShotEntry(models.Model):
    # NOTE: which session this belongs to.
    # One session has many shot entries (one per spot shot from).
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name='shots'
    )
    # NOTE: which spot on the court (matches the spot ids from your React app:
    # "lc3", "ft", "paint", etc.)
    spot = models.CharField(max_length=20)
    makes = models.IntegerField(default=0)
    attempts = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.spot}: {self.makes}/{self.attempts}"