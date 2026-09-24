from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from apps.core.models import SlugModel, SoftDeleteModel, TimeStampedModel
from apps.core.utils import UploadPath
from apps.core.validators import validate_bd_phone, validate_image_file

_min_zero = MinValueValidator(0)
_positive = MinValueValidator(Decimal("0.01"))


def _image(folder):
    return models.ImageField(upload_to=UploadPath(folder), validators=[validate_image_file], null=True, blank=True)


class Category(TimeStampedModel, SlugModel):
    """
    A product category. Categories nest without a depth limit via `parent`.

    A category is publicly visible only if it AND all of its ancestors are active
    (see `services.CategoryIndex`). Use `services` to move/delete categories: they keep the
    tree free of cycles and refuse to orphan products.
    """

    name = models.CharField(max_length=120)
    image = _image("categories")
    # PROTECT: the database refuses to delete a category that still has children. The
    # service layer offers "re-parent the children" or "block" instead of cascading.
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    seo_title = models.CharField(max_length=70, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"
        indexes = [models.Index(fields=["parent", "sort_order"])]
        constraints = [
            models.CheckConstraint(condition=~Q(parent=models.F("id")), name="category_not_own_parent"),
            # Sibling names are unique, ignoring case. Two constraints because NULL parents
            # (top-level categories) are never equal to each other in a unique index.
            models.UniqueConstraint(
                Lower("name"), "parent", name="category_unique_name_per_parent"
            ),
            models.UniqueConstraint(
                Lower("name"), condition=Q(parent__isnull=True), name="category_unique_name_top_level"
            ),
        ]

    def __str__(self):
        return self.name

    def product_count(self):
        """
        Number of products in this category.

        Module 4's `Product.categories` M2M must use `related_name="products"`; until then there
        is no such relation and this is 0. `services.delete_category` relies on it.
        """
        products = getattr(self, "products", None)
        return products.count() if products is not None else 0


class Brand(TimeStampedModel, SlugModel):
    name = models.CharField(max_length=120)
    logo = _image("brands")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), name="brand_unique_name")]

    def __str__(self):
        return self.name


class Tag(TimeStampedModel, SlugModel):
    name = models.CharField(max_length=60)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), name="tag_unique_name")]

    def __str__(self):
        return self.name


# --- Product catalog ---------------------------------------------------------------------


class SkinType(models.TextChoices):
    OILY = "oily", "Oily"
    DRY = "dry", "Dry"
    COMBINATION = "combination", "Combination"
    NORMAL = "normal", "Normal"
    SENSITIVE = "sensitive", "Sensitive"
    ALL = "all", "All skin types"


class SizeUnit(models.TextChoices):
    ML = "ml", "ml"
    L = "l", "L"
    G = "g", "g"
    KG = "kg", "kg"
    PCS = "pcs", "pcs"
    OZ = "oz", "oz"


class Gender(models.TextChoices):
    UNISEX = "unisex", "Unisex"
    WOMEN = "women", "Women"
    MEN = "men", "Men"
    KIDS = "kids", "Kids"


class ProductStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class StockStatus(models.TextChoices):
    IN_STOCK = "in_stock", "In stock"
    OUT_OF_STOCK = "out_of_stock", "Out of stock"
    BACKORDER = "backorder", "Backorder"


class Product(TimeStampedModel, SoftDeleteModel, SlugModel):
    """
    A sellable product.

    Price and stock fields here are the product's own (used directly when `has_variants` is
    False, and as the fallback for a variant that doesn't set its own). Stock is never edited
    directly outside `services.adjust_stock`, which keeps `StockMovement` a complete log and
    `stock_status` in sync.
    """

    name = models.CharField(max_length=200)
    short_description = models.CharField(max_length=300, blank=True)
    full_description = models.TextField(blank=True, help_text="Rich text/HTML")
    user_guide = models.TextField(blank=True, help_text="How to use, rich text/HTML")

    feature_image = models.ImageField(upload_to=UploadPath("products"), validators=[validate_image_file])

    categories = models.ManyToManyField(Category, through="ProductCategory", related_name="products", blank=True)
    brand = models.ForeignKey(Brand, null=True, blank=True, on_delete=models.SET_NULL, related_name="products")
    tags = models.ManyToManyField(Tag, related_name="products", blank=True)

    regular_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[_positive])
    discount_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[_min_zero])
    sale_start_at = models.DateTimeField(null=True, blank=True)
    sale_end_at = models.DateTimeField(null=True, blank=True)

    sku = models.CharField(max_length=64, unique=True)
    barcode = models.CharField(max_length=64, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    manage_stock = models.BooleanField(default=True)
    low_stock_threshold = models.PositiveIntegerField(
        null=True, blank=True, help_text="Blank uses the site-wide default from Site Settings."
    )
    stock_status = models.CharField(max_length=15, choices=StockStatus.choices, default=StockStatus.IN_STOCK, db_index=True)
    has_variants = models.BooleanField(default=False)

    skin_type = ArrayField(models.CharField(max_length=15, choices=SkinType.choices), blank=True, default=list)
    key_ingredients = ArrayField(models.CharField(max_length=100), blank=True, default=list, help_text="Short highlight list")
    ingredients = models.TextField(blank=True, help_text="Full ingredient list (INCI)")
    size_value = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, validators=[_min_zero])
    size_unit = models.CharField(max_length=5, choices=SizeUnit.choices, blank=True)
    country_of_origin = models.CharField(max_length=80, blank=True)
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True, help_text="Expiry date / shelf life (PAO)")
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)

    is_featured = models.BooleanField(default=False, db_index=True)
    is_new_arrival = models.BooleanField(default=False, db_index=True)
    is_bestseller = models.BooleanField(default=False, db_index=True)
    status = models.CharField(max_length=10, choices=ProductStatus.choices, default=ProductStatus.DRAFT, db_index=True)

    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=320, blank=True)
    og_image = models.ImageField(upload_to=UploadPath("products"), validators=[validate_image_file], null=True, blank=True)

    # Denormalized, updated by the Reviews service (Module 12). Read-only everywhere else.
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.00"))
    review_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["brand", "status"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(regular_price__gt=0), name="product_regular_price_positive"),
            models.CheckConstraint(
                condition=Q(discount_price__isnull=True) | Q(discount_price__lt=models.F("regular_price")),
                name="product_discount_price_lower",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def on_sale(self):
        if self.discount_price is None:
            return False
        now = timezone.now()
        if self.sale_start_at and now < self.sale_start_at:
            return False
        if self.sale_end_at and now > self.sale_end_at:
            return False
        return True

    @property
    def effective_price(self):
        return self.discount_price if self.on_sale else self.regular_price

    @property
    def discount_percentage(self):
        if not self.on_sale or not self.regular_price:
            return 0
        return int(round((self.regular_price - self.discount_price) / self.regular_price * 100))

    @property
    def in_stock(self):
        if not self.manage_stock:
            return True
        if self.stock_status == StockStatus.BACKORDER:
            return True
        return self.stock_quantity > 0

    @property
    def effective_low_stock_threshold(self):
        if self.low_stock_threshold is not None:
            return self.low_stock_threshold
        from apps.site_settings.services import get_site_settings

        return get_site_settings().low_stock_threshold

    @property
    def is_low_stock(self):
        return self.manage_stock and 0 < self.stock_quantity <= self.effective_low_stock_threshold


class ProductImage(TimeStampedModel):
    """One gallery image of a product. `sort_order` controls display order (0 first)."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=UploadPath("products"), validators=[validate_image_file])
    alt_text = models.CharField(max_length=150, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"Image {self.pk} of {self.product_id}"


class ProductCategory(models.Model):
    """Through model for `Product.categories`: exactly one category may be marked primary."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="category_links")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="product_links")
    is_primary = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "category"], name="product_category_unique"),
            models.UniqueConstraint(
                fields=["product"], condition=Q(is_primary=True), name="product_one_primary_category"
            ),
        ]

    def __str__(self):
        return f"{self.product_id} -> {self.category_id}"


class ProductAttribute(TimeStampedModel, SlugModel):
    """A reusable variant dimension, e.g. Shade, Size."""

    name = models.CharField(max_length=60)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), name="product_attribute_unique_name")]

    def __str__(self):
        return self.name


class AttributeValue(TimeStampedModel, SlugModel):
    """A value of a `ProductAttribute`, e.g. Rose (of Shade), 50ml (of Size). Reusable across products."""

    attribute = models.ForeignKey(ProductAttribute, on_delete=models.CASCADE, related_name="values")
    value = models.CharField(max_length=60)

    class Meta:
        ordering = ["value"]
        verbose_name_plural = "attribute values"
        constraints = [
            models.UniqueConstraint(Lower("value"), "attribute", name="attribute_value_unique_per_attribute"),
        ]

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


class ProductVariant(TimeStampedModel):
    """
    One buyable combination of attribute values for a product (e.g. Shade=Rose, Size=50ml).

    `option_signature` is maintained by `services.set_variant_options` (sorted attribute-value
    ids, joined) so the database can enforce "no two variants of the same product share the same
    combination of options" via a unique constraint, which a bare M2M cannot express.
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    attribute_values = models.ManyToManyField(AttributeValue, related_name="variants", blank=True)
    option_signature = models.CharField(max_length=255, editable=False, default="")

    sku = models.CharField(max_length=64, unique=True)
    regular_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[_min_zero])
    discount_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[_min_zero])
    stock_quantity = models.PositiveIntegerField(default=0)
    manage_stock = models.BooleanField(default=True)
    image = models.ImageField(upload_to=UploadPath("products"), validators=[validate_image_file], null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["product", "option_signature"], name="variant_unique_option_combo"),
            models.CheckConstraint(
                condition=Q(discount_price__isnull=True) | Q(regular_price__isnull=True) | Q(discount_price__lt=models.F("regular_price")),
                name="variant_discount_price_lower",
            ),
        ]

    def __str__(self):
        return self.sku

    def price_of(self, field):
        value = getattr(self, field)
        return value if value is not None else getattr(self.product, field)

    @property
    def regular_price_effective(self):
        return self.price_of("regular_price")

    @property
    def discount_price_effective(self):
        return self.discount_price if self.discount_price is not None else (
            self.product.discount_price if self.regular_price is None else None
        )

    @property
    def on_sale(self):
        return self.discount_price_effective is not None and self.product.on_sale

    @property
    def effective_price(self):
        return self.discount_price_effective if self.on_sale else self.regular_price_effective

    @property
    def in_stock(self):
        return True if not self.manage_stock else self.stock_quantity > 0


class StockMovement(TimeStampedModel):
    """
    An immutable log entry of every stock change, written by `services.adjust_stock`.

    Positive `quantity_change` restocks, negative sells/reduces. `balance_after` is the resulting
    on-hand quantity, recorded so history reads correctly even if later movements are added.
    """

    class Reason(models.TextChoices):
        SALE = "sale", "Sale"
        RETURN = "return", "Return"
        MANUAL = "manual", "Manual adjustment"
        RESTOCK = "restock", "Restock"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_movements")
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.CASCADE, related_name="stock_movements")
    quantity_change = models.IntegerField()
    balance_after = models.PositiveIntegerField()
    reason = models.CharField(max_length=10, choices=Reason.choices)
    reference = models.CharField(max_length=100, blank=True, help_text="e.g. an order number")
    note = models.CharField(max_length=255, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["product", "-created_at"])]

    def __str__(self):
        return f"{self.product_id}: {self.quantity_change:+d}"


class StockNotification(TimeStampedModel):
    """
    A "Notify Me" request: text `phone` when `product` (or one `variant` of it) is back in stock.

    `variant` null means "the product": for a product with variants, any of its variants coming back.
    `notified_at` is set once the alert has been sent; a sent request is kept as history, and the same
    phone can then subscribe again. `services.subscribe_to_restock` allows one pending request per
    product/variant/phone (checked under a lock on the product row).
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_notifications")
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.CASCADE, related_name="stock_notifications")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    phone = models.CharField(max_length=11, validators=[validate_bd_phone])
    notified_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["product", "notified_at"])]

    def __str__(self):
        return f"{self.phone} -> {self.variant or self.product}"
