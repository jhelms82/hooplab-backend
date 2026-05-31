from rest_framework.routers import DefaultRouter
from .views import PlayerViewSet, SessionViewSet, ShotEntryViewSet

# NOTE: A router auto-generates all the URLs for a ViewSet. Because we used
# ModelViewSet, each of these gets a full set of addresses (list, create,
# detail, update, delete) without us writing each one.
router = DefaultRouter()
router.register(r'players', PlayerViewSet, basename='player')
router.register(r'sessions', SessionViewSet, basename='session')
router.register(r'shots', ShotEntryViewSet, basename='shotentry')

urlpatterns = router.urls