from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from .models import Product, StockMovement
from .services import register_movement, InsufficientStockError


class CurrentQuantityTestCase(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='M6 Screw', price=0.50, minimum_quantity=10
        )

    def test_current_quantity_sums_in_and_out_movements(self):
        StockMovement.objects.create(product=self.product, type='IN', quantity=100)
        StockMovement.objects.create(product=self.product, type='OUT', quantity=30)
        self.assertEqual(self.product.current_quantity, 70)

    def test_low_stock_when_below_minimum(self):
        StockMovement.objects.create(product=self.product, type='IN', quantity=5)
        self.assertTrue(self.product.low_stock)


class ListingWithoutNPlusOneTestCase(TestCase):
    """Ensures the N+1 fix (architecture review) keeps holding."""

    def setUp(self):
        for i in range(5):
            product = Product.objects.create(
                name=f'Product {i}', price=10, minimum_quantity=5
            )
            StockMovement.objects.create(product=product, type='IN', quantity=50)

    def test_listing_uses_a_single_aggregation_query(self):
        with CaptureQueriesContext(connection) as ctx:
            products = list(Product.objects.with_current_quantity())
            for p in products:
                _ = p.current_qty  # already annotated, no new query fired

        # 1 query to fetch + annotate all products at once, regardless
        # of how many products exist.
        self.assertEqual(len(ctx.captured_queries), 1)


class RegisterMovementServiceTestCase(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='M6 Screw', price=0.50, minimum_quantity=10
        )
        StockMovement.objects.create(product=self.product, type='IN', quantity=20)

    def test_valid_out_movement_is_registered(self):
        register_movement(self.product.id, movement_type='OUT', quantity=5)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_quantity, 15)

    def test_out_movement_above_stock_raises_error(self):
        with self.assertRaises(InsufficientStockError):
            register_movement(self.product.id, movement_type='OUT', quantity=999)

        # No movement should be created when validation fails.
        self.assertEqual(self.product.movements.count(), 1)
