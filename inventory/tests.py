from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .forms import MovementForm, ProductForm
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


class LoginRequiredTestCase(TestCase):
    """Covers PRD §6.4: every inventory view requires authentication."""

    def setUp(self):
        self.product = Product.objects.create(
            name='M6 Screw', price=0.50, minimum_quantity=10
        )
        self.user = User.objects.create_user(username='juliana', password='senha-teste-123')

    def test_anonymous_request_is_redirected_to_login(self):
        response = self.client.get(reverse('product_list'))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('product_list')}"
        )

    def test_authenticated_request_succeeds(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('product_list'))
        self.assertEqual(response.status_code, 200)

    def test_anonymous_product_detail_is_redirected_to_login(self):
        url = reverse('product_detail', args=[self.product.id])
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")


class ProductFormTestCase(TestCase):
    """Covers PRD §6.1: price must be server-side validated as > 0."""

    def test_zero_price_is_rejected(self):
        form = ProductForm(data={
            'name': 'Parafuso', 'category': '', 'price': '0', 'minimum_quantity': 5,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('price', form.errors)

    def test_negative_price_is_rejected(self):
        form = ProductForm(data={
            'name': 'Parafuso', 'category': '', 'price': '-10', 'minimum_quantity': 5,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('price', form.errors)

    def test_valid_data_is_accepted(self):
        form = ProductForm(data={
            'name': 'Parafuso', 'category': '', 'price': '1.50', 'minimum_quantity': 5,
        })
        self.assertTrue(form.is_valid())


class MovementFormTestCase(TestCase):
    """Covers PRD §6.2/§8: quantity must be a positive integer."""

    def test_zero_quantity_is_rejected(self):
        form = MovementForm(data={'type': 'IN', 'quantity': '0', 'reason': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('quantity', form.errors)

    def test_non_numeric_quantity_is_rejected(self):
        form = MovementForm(data={'type': 'IN', 'quantity': 'abc', 'reason': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('quantity', form.errors)

    def test_valid_data_is_accepted(self):
        form = MovementForm(data={'type': 'OUT', 'quantity': '3', 'reason': 'Venda'})
        self.assertTrue(form.is_valid())
