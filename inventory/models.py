from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum, Case, When, IntegerField, F


class ProductQuerySet(models.QuerySet):
    def with_current_quantity(self):
        """Annotates each product with its current stock quantity in a
        single aggregation query, instead of triggering one query per
        product (the classic N+1 problem that happens when the
        `current_quantity` property is used inside a loop/listing).
        """
        return self.annotate(
            current_qty=Sum(
                Case(
                    When(movements__type=StockMovement.IN, then='movements__quantity'),
                    When(movements__type=StockMovement.OUT, then=-1 * F('movements__quantity')),
                    default=0,
                    output_field=IntegerField(),
                )
            )
        )


class Product(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_quantity = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        """Human-readable label used in admin lists and shell debugging."""
        return self.name

    @property
    def current_quantity(self):
        """Calculates the stock quantity from the movement history.

        Recommended usage: only for a SINGLE product (e.g. detail
        page). In listings with multiple products, use
        `Product.objects.with_current_quantity()` to avoid N+1 - each
        access to this property triggers an aggregation query.
        """
        result = self.movements.aggregate(
            total=Sum(
                Case(
                    When(type=StockMovement.IN, then='quantity'),
                    When(type=StockMovement.OUT, then=-1 * F('quantity')),
                    output_field=IntegerField(),
                )
            )
        )
        return result['total'] or 0

    @property
    def low_stock(self):
        """True when stock is below the configured minimum.

        Drives the PRD §6.5 low-stock visual indicator in the listing
        without the template needing to know the comparison rule.
        """
        return self.current_quantity < self.minimum_quantity


class StockMovement(models.Model):
    IN = 'IN'
    OUT = 'OUT'
    TYPE_CHOICES = [
        (IN, 'In'),
        (OUT, 'Out'),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='movements'
    )
    type = models.CharField(max_length=3, choices=TYPE_CHOICES)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    date = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=200, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements',
    )

    class Meta:
        indexes = [
            models.Index(fields=['product', 'date']),
        ]
        # DB-level backstop for the two business rules that MovementForm
        # already enforces (PRD §6.2) - a form is only checked on the one
        # view that uses it; a constraint holds even if a movement is
        # written through the admin, the shell, or a future API/import
        # path that bypasses the form entirely.
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gt=0),
                name='stockmovement_quantity_positive',
            ),
            models.CheckConstraint(
                check=models.Q(type__in=['IN', 'OUT']),
                name='stockmovement_type_valid',
            ),
        ]

    def __str__(self):
        """Human-readable label used in admin lists and shell debugging."""
        return f'{self.get_type_display()} - {self.product.name} ({self.quantity})'
