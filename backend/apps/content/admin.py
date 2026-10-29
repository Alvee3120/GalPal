from django.contrib import admin

from .models import Announcement, Faq, HomepageCategorySection, NewsletterSubscriber, Page


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "is_active", "updated_at"]
    list_filter = ["is_active"]
    search_fields = ["title", "slug"]


@admin.register(Faq)
class FaqAdmin(admin.ModelAdmin):
    list_display = ["question", "category", "sort_order", "is_active"]
    list_filter = ["is_active", "category"]
    search_fields = ["question", "answer"]


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ["email", "phone", "is_subscribed", "source", "created_at"]
    list_filter = ["is_subscribed"]
    search_fields = ["email", "phone"]
    exclude = ["token"]


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ["text", "is_active", "starts_at", "ends_at", "sort_order"]
    list_filter = ["is_active"]


@admin.register(HomepageCategorySection)
class HomepageCategorySectionAdmin(admin.ModelAdmin):
    list_display = ["__str__", "source", "position", "sort_order", "product_limit", "rows", "is_active"]
    list_filter = ["source", "position", "is_active"]
