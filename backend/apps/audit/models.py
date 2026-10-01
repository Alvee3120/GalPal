"""
Audit log (Module 18): who did what, with before/after and the IP, for every Admin / CCE write.

Two kinds of entries:
* **request** entries (`api.post`, `api.patch`, …), written by `middleware.AuditMiddleware` for every successful or
  refused write under /api/v1/admin/ by a staff member — the raw trail, with the request body (secrets redacted);
* **event** entries (`order.created`, `order.status_changed`, `shipping.zone_charge_changed`, …) with the business
  meaning and a `changes` diff, written by the services/signals where those things happen.
Append-only: nothing in the app edits or deletes entries.
"""

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    actor_name = models.CharField(max_length=150, blank=True, help_text="Kept if the account is later deleted.")
    actor_role = models.CharField(max_length=10, blank=True)
    action = models.CharField(max_length=60, db_index=True)
    target_type = models.CharField(max_length=40, blank=True, db_index=True)
    target_id = models.CharField(max_length=40, blank=True, db_index=True)
    target_label = models.CharField(max_length=200, blank=True)
    changes = models.JSONField(default=dict, blank=True, help_text='{"field": [before, after]}')
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    method = models.CharField(max_length=7, blank=True)
    path = models.CharField(max_length=300, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["actor", "-created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor_name or 'system'} {self.action}"
