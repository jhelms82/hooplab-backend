from django.contrib import admin

# Register your models here.

from django.contrib import admin
from .models import Player, Session, ShotEntry

admin.site.register(Player)
admin.site.register(Session)
admin.site.register(ShotEntry)