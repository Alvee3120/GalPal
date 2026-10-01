from django.contrib import admin

from .models import CheckoutLead, ContactMessage, ContactMessageNote, CustomerNote, CustomerTag, ReturnRequest


@admin.register(CustomerTag)
class CustomerTagAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]
    filter_horizontal = ["customers"]


@admin.register(CustomerNote)
class CustomerNoteAdmin(admin.ModelAdmin):
    list_display = ["customer", "author", "created_at"]
    raw_id_fields = ["customer", "author"]


class ContactMessageNoteInline(admin.TabularInline):
    model = ContactMessageNote
    extra = 0
    raw_id_fields = ["author"]


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "email", "subject", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["name", "phone", "email", "subject"]
    inlines = [ContactMessageNoteInline]


@admin.register(CheckoutLead)
class CheckoutLeadAdmin(admin.ModelAdmin):
    list_display = ["phone", "name", "status", "cart_value", "updated_at"]
    list_filter = ["status"]
    search_fields = ["phone", "name", "email"]


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ["order", "customer", "reason", "status", "created_at"]
    list_filter = ["status", "reason"]
    raw_id_fields = ["order", "customer", "handled_by"]
