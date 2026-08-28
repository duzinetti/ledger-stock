"""
Service layer for the inventory app.

Centralizes business rules that shouldn't be scattered across views
and a future API - this way the HTML view, REST API, and future
async tasks (e.g. Celery) call the same function and get the same
behavior, without duplicating validation.
"""
from django.db import transaction

from .models import MovementType, Product, StockMovement


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


class InvalidQuantityError(Exception):
    """Raised when a movement quantity is not a positive integer."""

    def __init__(self, quantity):
        self.quantity = quantity
        super().__init__(
            f'Invalid quantity: {quantity}. Quantity must be greater than zero.'
        )


class InvalidMovementTypeError(Exception):
    """Raised when a movement type is not IN or OUT."""

    def __init__(self, movement_type):
        self.movement_type = movement_type
        super().__init__(
            f'Invalid movement type: "{movement_type}". Must be "IN" or "OUT".'
        )


class InactiveProductError(Exception):
    """Raised when a movement is attempted on a soft-deleted product that
    has already been drawn down to zero - active=False products still
    holding stock may keep receiving movements until that stock is
    reconciled, but a fully wound-down product accepts no further activity.
    """

    def __init__(self, product):
        self.product = product
        super().__init__(
            f'Product "{product.name}" is inactive and has no stock left to move.'
        )


def register_movement(product_id, movement_type, quantity, reason='', user=None):
    """Registers a stock movement safely under concurrent access.

    Uses select_for_update() inside a transaction to lock the
    product row while validating and writing. This prevents two
    simultaneous requests from reading the same available quantity
    and both passing the stock-out validation - which would produce
    negative stock (a classic race condition in systems with
    concurrent access).

    Caveat: select_for_update() is a documented no-op on SQLite (the
    dev database) - it silently degrades to a plain SELECT with no
    row lock. This function's core safety guarantee is only real on
    a backend that supports row locking (Postgres, MySQL - see
    ConcurrentStockMovementTestCase, gated on
    connection.features.has_select_for_update).
    """
    if quantity <= 0: 
        raise InvalidQuantityError(
            quantity
        )
    
    if movement_type not in (MovementType.IN, MovementType.OUT):
        raise InvalidMovementTypeError(
            movement_type
        )

    with transaction.atomic():
        product = Product.objects.select_for_update().get(id=product_id)

        if not product.active and product.current_quantity <= 0:
            raise InactiveProductError(product)

        if movement_type == MovementType.OUT and quantity > product.current_quantity:
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
