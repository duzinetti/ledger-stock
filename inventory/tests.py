from django.contrib.auth.models import User
from django.db import connection, transaction
from django.db.utils import IntegrityError
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.db.models import ProtectedError

from .forms import MovementForm, ProductForm
from .models import Product, StockMovement
from .services import (
    register_movement,
    InactiveProductError,
    InsufficientStockError,
    InvalidMovementTypeError,
    InvalidQuantityError,
)

from unittest.mock import patch
import threading


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

    def test_with_current_quantity_for_product_with_no_movements(self):
        annotated = Product.objects.with_current_quantity().get(id=self.product.id)
        self.assertEqual(annotated.current_qty, 0)
        self.assertTrue(annotated.is_low_stock)


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

    def test_admin_changelist_does_not_reintroduce_n_plus_one(self):
        """Covers #28: ProductAdmin.list_display used to call the
        current_quantity/low_stock properties, each firing a fresh
        aggregation query per row."""
        superuser = User.objects.create_superuser(
            username='admin', password='senha-teste-123', email='admin@example.com'
        )
        self.client.force_login(superuser)

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get('/admin/inventory/product/')

        self.assertEqual(response.status_code, 200)
        # A handful of admin bookkeeping queries (session, permissions,
        # count) are expected - the point is this doesn't scale with
        # the number of products (5 here). A regression back to the
        # properties would add ~2 extra queries per row.
        self.assertLess(len(ctx.captured_queries), 10)


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

    def test_out_movement_exactly_equal_to_stock_is_allowed(self):
        register_movement(self.product.id, movement_type='OUT', quantity=20)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_quantity, 0)

    def test_zero_quantity_is_rejected_at_service_layer(self):
        with self.assertRaises(InvalidQuantityError):
            register_movement(self.product.id, movement_type='IN', quantity=0)

        self.assertEqual(self.product.movements.count(), 1)

    def test_invalid_quantity_is_rejected(self):
        with self.assertRaises(InvalidQuantityError):
            register_movement(self.product.id, movement_type='IN', quantity=-5)

        # No movement should be created when validation fails.
        self.assertEqual(self.product.movements.count(), 1)

    def test_invalid_movement_type_is_rejected(self):
        with self.assertRaises(InvalidMovementTypeError):
            register_movement(self.product.id, movement_type='XYZ', quantity=5)

        self.assertEqual(self.product.movements.count(), 1)

    def test_movement_on_inactive_product_with_stock_is_allowed(self):
        # active=False products may still be drawn down until reconciled
        # to zero - self.product has 20 units from setUp.
        self.product.active = False
        self.product.save(update_fields=['active'])

        register_movement(self.product.id, movement_type='OUT', quantity=5)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_quantity, 15)

    def test_movement_on_inactive_product_without_stock_is_blocked(self):
        empty_product = Product.objects.create(
            name='Discontinued Widget', price=1, minimum_quantity=0, active=False
        )
        with self.assertRaises(InactiveProductError):
            register_movement(empty_product.id, movement_type='IN', quantity=5)

        self.assertEqual(empty_product.movements.count(), 0)


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


class StockMovementConstraintsTestCase(TestCase):
    """Covers the DB-level backstop for a write that bypasses MovementForm
    entirely (e.g. shell, admin, future API) - PRD §6.2/§8.
    """

    def setUp(self):
        self.product = Product.objects.create(
            name='M6 Screw', price=0.50, minimum_quantity=10
        )

    def test_non_positive_quantity_is_rejected_at_db_level(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.create(product=self.product, type='IN', quantity=0)

    def test_negative_quantity_is_rejected_at_db_level(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.create(product=self.product, type='IN', quantity=-5)

    def test_invalid_type_is_rejected_at_db_level(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.create(product=self.product, type='XX', quantity=5)


class ProductSoftDeleteTestCase(TestCase):
    """Covers PRD §8/§10.2's soft-delete decision: a "deleted" product is
    deactivated (active=False), never physically removed, so its
    StockMovement history stays intact for audit purposes.
    """

    def setUp(self):
        self.product = Product.objects.create(
            name='M6 Screw', price=0.50, minimum_quantity=10
        )
        StockMovement.objects.create(product=self.product, type='IN', quantity=10)
        self.user = User.objects.create_user(username='juliana', password='senha-teste-123')
        self.client.force_login(self.user)

    def test_delete_view_deactivates_instead_of_removing_the_row(self):
        self.client.post(reverse('product_delete', args=[self.product.id]))

        self.product.refresh_from_db()
        self.assertFalse(self.product.active)
        self.assertTrue(Product.objects.filter(id=self.product.id).exists())

    def test_inactive_product_is_excluded_from_listing(self):
        self.product.active = False
        self.product.save(update_fields=['active'])

        response = self.client.get(reverse('product_list'))
        self.assertNotContains(response, self.product.name)

    def test_inactive_product_detail_is_still_accessible_with_history(self):
        self.product.active = False
        self.product.save(update_fields=['active'])

        response = self.client.get(reverse('product_detail', args=[self.product.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)
        self.assertEqual(len(response.context['movements']), 1)


class ProductDeletionProtectionTestCase(TestCase):
    """Covers the DB-level backstop for product history: on_delete=PROTECT
    on StockMovement.product means the database itself refuses to delete
    a Product that still has movements, no matter which code path tries
    (admin, shell, a future script) - not just the product_delete view,
    which already avoids physical deletion by design (see
    ProductSoftDeleteTestCase).
    """

    def test_deleting_a_product_with_movements_is_blocked_at_db_level(self):
        product = Product.objects.create(
            name='M6 Screw', price=0.50, minimum_quantity=10
        )
        StockMovement.objects.create(product=product, type='IN', quantity=10)

        with self.assertRaises(ProtectedError):
            product.delete()

        self.assertTrue(Product.objects.filter(id=product.id).exists())

    def test_deleting_a_product_with_no_movements_is_allowed(self):
        product = Product.objects.create(
            name='Never Sold Widget', price=1, minimum_quantity=0
        )

        product.delete()

        self.assertFalse(Product.objects.filter(id=product.id).exists())


class StockMovementAdminPermissionsTestCase(TestCase):
    """Covers audit-trail-tampering: the movement log must be read-only
    in admin, since add/change bypass services.register_movement().
    """

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='admin', password='senha-teste-123', email='admin@example.com'
        )
        self.product = Product.objects.create(
            name='M6 Screw', price=0.50, minimum_quantity=10
        )
        self.movement = StockMovement.objects.create(
            product=self.product, type='IN', quantity=10
        )
        self.client.force_login(self.superuser)

    def test_add_is_blocked(self):
        response = self.client.get('/admin/inventory/stockmovement/add/')
        self.assertEqual(response.status_code, 403)

    def test_change_view_is_read_only(self):
        # Django renders the change page in read-only mode (200, no save
        # button) rather than 403 when has_view_permission is True but
        # has_change_permission is False - the real enforcement is that
        # a POST can't actually alter the record, checked below.
        response = self.client.get(f'/admin/inventory/stockmovement/{self.movement.id}/change/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="_save"')

    def test_change_post_does_not_alter_the_record(self):
        url = f'/admin/inventory/stockmovement/{self.movement.id}/change/'
        self.client.post(url, {
            'product': self.product.id, 'type': 'IN', 'quantity': 999, 'reason': '',
        })
        self.movement.refresh_from_db()
        self.assertEqual(self.movement.quantity, 10)

    def test_delete_is_blocked(self):
        response = self.client.get(f'/admin/inventory/stockmovement/{self.movement.id}/delete/')
        self.assertEqual(response.status_code, 403)

    def test_list_view_is_still_accessible(self):
        response = self.client.get('/admin/inventory/stockmovement/')
        self.assertEqual(response.status_code, 200)


class MovementCreateRaceConditionTestCase(TestCase):
    """Covers #22: Product.DoesNotExist inside register_movement() must not surface as an unhandled 500."""

    def setUp(self):
        self.product = Product.objects.create(
            name='M6 Screw', price=0.50, minimum_quantity=10
        )
        self.user = User.objects.create_user(username='juliana', password='senha-teste-123')
        self.client.force_login(self.user)

    def test_product_deleted_between_view_lookup_and_service_call(self):
        url = reverse('movement_create', args=[self.product.id])
        post_data = {'type': 'IN', 'quantity': 5, 'reason': 'Reposição'}

        with patch('inventory.views.register_movement_service', side_effect=Product.DoesNotExist):
            response = self.client.post(url, post_data, follow=True)

        self.assertRedirects(response, reverse('product_list'))
        self.assertContains(
            response,
            'Este produto não existe mais - não foi possível registrar a movimentação.'
        )


class ProductConstraintsTestCase(TestCase):
    """Covers the DB-level backstop for Product, bypassing ProductForm entirely (e.g. shell, admin, future API)."""

    def test_non_positive_price_is_rejected_at_db_level(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(name='X', price=0, minimum_quantity=5)

    def test_negative_price_is_rejected_at_db_level(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(name='X', price=-10, minimum_quantity=5)

    def test_negative_minimum_quantity_is_rejected_at_db_level(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(name='X', price=10, minimum_quantity=-1)


class ConcurrentStockMovementTestCase(TransactionTestCase):
    """Covers #24: proves (or would prove) that select_for_update() actually prevents overselling under real concurrent writes - not exercised on SQLite, where the feature is a documented no-op (see docstring in services.register_movement())."""

    def setUp(self):
        self.product = Product.objects.create(
            name='M6 Screw', price=0.50, minimum_quantity=10
        )
        StockMovement.objects.create(product=self.product, type='IN', quantity=20)

    @skipUnlessDBFeature('has_select_for_update')
    def test_concurrent_out_movements_do_not_oversell_stock(self):
        barrier = threading.Barrier(2)
        errors = []

        def worker():
            barrier.wait()
            try:
                register_movement(
                    self.product.id,
                    movement_type='OUT',
                    quantity=15,
                )
            except InsufficientStockError:
                pass  # esperado para UMA das duas threads, se a trava funcionar
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.product.refresh_from_db()
        self.assertGreaterEqual(self.product.current_quantity, 0)


class MovementCreateViewTestCase(TestCase):
    """Covers #25: movement_create had zero test coverage via HTTP."""

    def setUp(self):
        self.product = Product.objects.create(
            name='M6 screw', price=0.50, minimum_quantity=10
        )
        StockMovement.objects.create(product=self.product, type='IN', quantity=20) 
        self.user = User.objects.create_user(username='juliana', password='senha-teste-123')
        self.client.force_login(self.user)
        self.url = reverse('movement_create', args=[self.product.id])

    def test_get_renders_the_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_valid_in_movement_creates_stock_movement_and_redirects(self):
        response = self.client.post(self.url, {
            'type': 'IN', 'quantity': 5, 'reason': 'Reposição',
        })

        self.assertEqual(self.product.movements.count(), 2)  # 1 do setUp + 1 do POST
        self.assertRedirects(
            response, reverse('product_detail', args=[self.product.id])
        )

    def test_valid_out_movement_within_stock_creates_stock_movement(self):
        response = self.client.post(self.url, {
            'type': 'OUT', 'quantity': 20, 'reason': 'Retirada'
        })

        self.assertEqual(self.product.movements.count(), 2)
        self.assertRedirects(
            response, reverse('product_detail', args=[self.product.id])
        )

    def test_invalid_form_data_does_not_create_movement(self):
        response = self.client.post(self.url, {
            'type': 'IN', 'quantity': 0, 'reason': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.product.movements.count(), 1)

    def test_insufficient_stock_shows_error_and_redirects_to_detail(self):
        response = self.client.post(self.url, {
            'type': 'OUT', 'quantity': 999, 'reason': '',
        }, follow=True)

        self.assertRedirects(
            response, reverse('product_detail', args=[self.product.id])
        )
        self.assertContains(response, 'Quantidade de saída maior que o estoque disponível')
        self.assertEqual(self.product.movements.count(), 1)

    def test_anonymous_request_is_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('login')}?next={self.url}")

    def test_invalid_quantity_error_shows_error_and_redirects_to_detail(self):
        with patch('inventory.views.register_movement_service', side_effect=InvalidQuantityError(-5)):
            response = self.client.post(self.url, {
                'type': 'IN', 'quantity': 5, 'reason': '',
            }, follow=True)

        self.assertRedirects(response, reverse('product_detail', args=[self.product.id]))
        self.assertContains(response, 'Quantidade inválida')

    def test_invalid_movement_type_error_shows_error_and_redirects_to_detail(self):
        with patch('inventory.views.register_movement_service', side_effect=InvalidMovementTypeError('XX')):
            response = self.client.post(self.url, {
                'type': 'IN', 'quantity': 5, 'reason': '',
            }, follow=True)

        self.assertRedirects(response, reverse('product_detail', args=[self.product.id]))
        self.assertContains(response, 'Tipo de movimentação inválido')