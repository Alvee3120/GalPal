"""
Content & storefront extras (Module 15, Admin only): CMS pages (About, policies…), FAQs, newsletter subscribers and the
announcement bar. Page content is a small Markdown subset (headings, lists, bold, links) that the storefront renders as
plain React elements — never as raw HTML — so nothing an editor types can run as script.
"""

import secrets

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


class Page(TimeStampedModel):
    """A storefront content page, addressed by slug (e.g. `about`, `privacy-policy`, `shipping-policy`)."""

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, unique=True)
    content = models.TextField(max_length=60000, help_text="Markdown subset: ## headings, - lists, **bold**, [links](url).")
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class Faq(TimeStampedModel):
    category = models.CharField(max_length=60, blank=True, help_text="Groups questions on the FAQ page, e.g. Orders, Delivery.")
    question = models.CharField(max_length=300)
    answer = models.TextField(max_length=5000)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["category", "sort_order", "id"]
        verbose_name = "FAQ"

    def __str__(self):
        return self.question


def _unsubscribe_token():
    return secrets.token_urlsafe(24)


class NewsletterSubscriber(TimeStampedModel):
    """
    A newsletter sign-up by email and/or phone. `token` goes into the unsubscribe link of every newsletter (Module 16)
    so anyone holding the message can opt out, without logging in and without being able to opt out someone else.
    """

    email = models.EmailField(max_length=254, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    is_subscribed = models.BooleanField(default=True, db_index=True)
    source = models.CharField(max_length=30, blank=True, help_text="Where they signed up, e.g. footer.")
    token = models.CharField(max_length=64, unique=True, default=_unsubscribe_token, editable=False)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["email"], condition=Q(email__isnull=False), name="newsletter_unique_email"),
            models.UniqueConstraint(fields=["phone"], condition=Q(phone__isnull=False), name="newsletter_unique_phone"),
            models.CheckConstraint(condition=Q(email__isnull=False) | Q(phone__isnull=False), name="newsletter_email_or_phone"),
        ]

    def __str__(self):
        return self.email or self.phone


class Announcement(TimeStampedModel):
    """A line of text in the bar above the storefront navbar, optionally linked and limited to a time window."""

    text = models.CharField(max_length=200)
    link_url = models.CharField(max_length=300, blank=True, help_text="A site path (/shop) or an http(s) URL.")
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]

    def __str__(self):
        return self.text
