"""
Service layer for the inventory app.

Centralizes business rules that shouldn't be scattered across views
and a future API - this way the HTML view, REST API, and future
async tasks (e.g. Celery) call the same function and get the same
behavior, without duplicating validation.
"""
from django.db import transaction

from .models import Product, StockMovement


class InsufficientStockError(Exception):
    """Raised when a stock-out exceeds the available quantity."""

    def __init__(self, product, requested_quantity, available_quantity):
        self.product = product
        self.requested_quantity = requested_quantity
        self.available_quantity = available_quantity
        super().__init__(
            f'Insufficient stock for "{product.name}": '
            f'requested {requested_quantity}, available {available_quantity}.'
        )


def register_movement(product_id, movement_type, quantity, reason='', user=None):
    """Registers a stock movement safely under concurrent access.

    Uses select_for_update() inside a transaction to lock the
    product row while validating and writing. This prevents two
    simultaneous requests from reading the same available quantity
    and both passing the stock-out validation - which would produce
    negative stock (a classic race condition in systems with
    concurrent access).
    """
    with transaction.atomic():
        product = Product.objects.select_for_update().get(id=product_id)

        if movement_type == StockMovement.OUT and quantity > product.current_quantity:
            raise InsufficientStockError(
                product, quantity, product.current_quantity
            )

        movement = StockMovement.objects.create(
            product=product,
            type=movement_type,
            quantity=quantity,
            reason=reason,
            user=user,
        )

    return movement
