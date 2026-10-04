"""Public content endpoints (Module 15), mounted at /api/v1/."""
from django.urls import path

from .views import (
    AnnouncementListView,
    FaqListView,
    HomepageCategorySectionListView,
    NewsletterSubscribeView,
    NewsletterUnsubscribeView,
    PageDetailView,
    SearchView,
)

app_name = "content"

urlpatterns = [
    path("pages/<slug:slug>/", PageDetailView.as_view(), name="page"),
    path("faqs/", FaqListView.as_view(), name="faqs"),
    path("homepage/category-sections/", HomepageCategorySectionListView.as_view(), name="homepage-category-sections"),
    path("announcements/", AnnouncementListView.as_view(), name="announcements"),
    path("newsletter/subscribe/", NewsletterSubscribeView.as_view(), name="newsletter-subscribe"),
    path("newsletter/unsubscribe/", NewsletterUnsubscribeView.as_view(), name="newsletter-unsubscribe"),
    path("search/", SearchView.as_view(), name="search"),
]
