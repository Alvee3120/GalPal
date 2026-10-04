"""Content admin endpoints (Module 15), mounted at /api/v1/admin/. Admin only (CCE gets 403)."""
from rest_framework.routers import SimpleRouter

from .views_admin import AnnouncementViewSet, FaqViewSet, HomepageCategorySectionViewSet, PageViewSet, SubscriberViewSet

router = SimpleRouter()
router.register("content/pages", PageViewSet, basename="content-page")
router.register("content/faqs", FaqViewSet, basename="content-faq")
router.register("content/newsletter", SubscriberViewSet, basename="content-subscriber")
router.register("content/announcements", AnnouncementViewSet, basename="content-announcement")
router.register("content/category-sections", HomepageCategorySectionViewSet, basename="content-category-section")

urlpatterns = router.urls
