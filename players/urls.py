from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    PlayerViewSet,
    SessionViewSet,
    ShotEntryViewSet,
    request_password_reset,
    confirm_password_reset,
    forgot_username,
    debug_users,
)

# NOTE: A router auto-generates all the URLs for a ViewSet. Because we used
# ModelViewSet, each of these gets a full set of addresses (list, create,
# detail, update, delete) without us writing each one.
router = DefaultRouter()
router.register(r'players', PlayerViewSet, basename='player')
router.register(r'sessions', SessionViewSet, basename='session')
router.register(r'shots', ShotEntryViewSet, basename='shotentry')

# NOTE: the router builds the viewset URLs; we add our own function-based
# endpoints (password reset + forgot username) by hand below, then combine.
urlpatterns = router.urls + [
    path('password-reset/', request_password_reset),
    path('password-reset-confirm/', confirm_password_reset),
    path('forgot-username/', forgot_username),
    path('debug-users/', debug_users),  # TEMPORARY — delete after debugging
]