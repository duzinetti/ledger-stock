import os
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import connection, transaction
from django.db.utils import IntegrityError
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.db.models import ProtectedError

from .forms import MovementForm, ProductForm
from .models import Company, Membership, Product, StockMovement
from .services import (
    register_movement,
    create_employee,
    reset_employee_password,
    InactiveProductError,
    InsufficientStockError,
    InvalidMovementTypeError,
    InvalidQuantityError,
)

from unittest.mock import patch
import threading


class CurrentQuantityTestCase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Empresa Teste')
        self.product = Product.objects.create(
            company=self.company, name='M6 Screw', price=0.50, minimum_quantity=10
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
        self.company = Company.objects.create(name='Empresa Teste')
        for i in range(5):
            product = Product.objects.create(
                company=self.company, name=f'Product {i}', price=10, minimum_quantity=5
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
        self.company = Company.objects.create(name='Empresa Teste')
        self.product = Product.objects.create(
            company=self.company, name='M6 Screw', price=0.50, minimum_quantity=10
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
            company=self.company, name='Discontinued Widget', price=1, minimum_quantity=0, active=False
        )
        with self.assertRaises(InactiveProductError):
            register_movement(empty_product.id, movement_type='IN', quantity=5)

        self.assertEqual(empty_product.movements.count(), 0)


class LoginRequiredTestCase(TestCase):
    """Covers PRD §6.4: every inventory view requires authentication."""

    def setUp(self):
        self.company = Company.objects.create(name='Empresa Teste')
        self.product = Product.objects.create(
            company=self.company, name='M6 Screw', price=0.50, minimum_quantity=10
        )
        self.user = User.objects.create_user(username='juliana', password='senha-teste-123')
        Membership.objects.create(user=self.user, company=self.company)

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


class ProductCreateViewTestCase(TestCase):
    """Covers a gap found while implementing #17: ProductForm doesn't
    expose `company` (the logged-in user should never pick it), but
    nothing was assigning it either - product_create crashed with an
    IntegrityError on every submission, and no test caught it."""

    def setUp(self):
        self.company = Company.objects.create(name='Empresa Teste')
        self.user = User.objects.create_user(username='juliana', password='senha-teste-123')
        Membership.objects.create(user=self.user, company=self.company)
        self.client.force_login(self.user)

    def test_valid_post_creates_product_assigned_to_the_users_company(self):
        response = self.client.post(reverse('product_create'), {
            'name': 'Parafuso', 'category': '', 'price': '1.50', 'minimum_quantity': 5,
        })

        self.assertRedirects(response, reverse('product_list'))
        product = Product.objects.get(name='Parafuso')
        self.assertEqual(product.company, self.company)


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
        self.company = Company.objects.create(name='Empresa Teste')
        self.product = Product.objects.create(
            company=self.company, name='M6 Screw', price=0.50, minimum_quantity=10
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
        self.company = Company.objects.create(name='Empresa Teste')
        self.product = Product.objects.create(
            company=self.company, name='M6 Screw', price=0.50, minimum_quantity=10
        )
        StockMovement.objects.create(product=self.product, type='IN', quantity=10)
        self.user = User.objects.create_user(username='juliana', password='senha-teste-123')
        Membership.objects.create(user=self.user, company=self.company)
        gestor_group = Group.objects.get(name='Gestor')
        self.user.groups.add(gestor_group)
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

    def setUp(self):
        self.company = Company.objects.create(name='Empresa Teste')

    def test_deleting_a_product_with_movements_is_blocked_at_db_level(self):
        product = Product.objects.create(
            company=self.company, name='M6 Screw', price=0.50, minimum_quantity=10
        )
        StockMovement.objects.create(product=product, type='IN', quantity=10)

        with self.assertRaises(ProtectedError):
            product.delete()

        self.assertTrue(Product.objects.filter(id=product.id).exists())

    def test_deleting_a_product_with_no_movements_is_allowed(self):
        product = Product.objects.create(
            company=self.company, name='Never Sold Widget', price=1, minimum_quantity=0
        )

        product.delete()

        self.assertFalse(Product.objects.filter(id=product.id).exists())


class StockMovementAdminPermissionsTestCase(TestCase):
    """Covers audit-trail-tampering: the movement log must be read-only
    in admin, since add/change bypass services.register_movement().
    """

    def setUp(self):
        self.company = Company.objects.create(name='Empresa Teste')
        self.superuser = User.objects.create_superuser(
            username='admin', password='senha-teste-123', email='admin@example.com'
        )
        self.product = Product.objects.create(
            company=self.company, name='M6 Screw', price=0.50, minimum_quantity=10
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
        self.company = Company.objects.create(name='Empresa Teste')
        self.product = Product.objects.create(
            company=self.company, name='M6 Screw', price=0.50, minimum_quantity=10
        )
        self.user = User.objects.create_user(username='juliana', password='senha-teste-123')
        Membership.objects.create(user=self.user, company=self.company)
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

    def setUp(self):
        self.company = Company.objects.create(name='Empresa Teste')

    def test_non_positive_price_is_rejected_at_db_level(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(company=self.company, name='X', price=0, minimum_quantity=5)

    def test_negative_price_is_rejected_at_db_level(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(company=self.company, name='X', price=-10, minimum_quantity=5)

    def test_negative_minimum_quantity_is_rejected_at_db_level(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(company=self.company, name='X', price=10, minimum_quantity=-1)


class ConcurrentStockMovementTestCase(TransactionTestCase):
    """Covers #24: proves (or would prove) that select_for_update() actually prevents overselling under real concurrent writes - not exercised on SQLite, where the feature is a documented no-op (see docstring in services.register_movement())."""

    def setUp(self):
        self.company = Company.objects.create(name='Empresa Teste')
        self.product = Product.objects.create(
            company=self.company, name='M6 Screw', price=0.50, minimum_quantity=10
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
            finally:
                connection.close()

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
        self.company = Company.objects.create(name='Empresa Teste')
        self.product = Product.objects.create(
            company=self.company, name='M6 screw', price=0.50, minimum_quantity=10
        )
        StockMovement.objects.create(product=self.product, type='IN', quantity=20)
        self.user = User.objects.create_user(username='juliana', password='senha-teste-123')
        Membership.objects.create(user=self.user, company=self.company)
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
            response, reverse('product_update', args=[self.product.id])
        )

    def test_valid_out_movement_within_stock_creates_stock_movement(self):
        response = self.client.post(self.url, {
            'type': 'OUT', 'quantity': 20, 'reason': 'Retirada'
        })

        self.assertEqual(self.product.movements.count(), 2)
        self.assertRedirects(
            response, reverse('product_update', args=[self.product.id])
        )

    def test_invalid_form_data_does_not_create_movement(self):
        response = self.client.post(self.url, {
            'type': 'IN', 'quantity': 0, 'reason': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.product.movements.count(), 1)

    def test_insufficient_stock_shows_inline_error_on_product_update(self):
        response = self.client.post(self.url, {
            'type': 'OUT', 'quantity': 999, 'reason': '',
        })

        # Não redireciona mais - o erro vira form.add_error() e a
        # própria view já renderiza product_update.html na resposta.
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Quantidade de saída maior que o estoque disponível')
        self.assertEqual(self.product.movements.count(), 1)

    def test_anonymous_request_is_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('login')}?next={self.url}")

    def test_invalid_quantity_error_shows_inline_error_on_product_update(self):
        with patch('inventory.views.register_movement_service', side_effect=InvalidQuantityError(-5)):
            response = self.client.post(self.url, {
                'type': 'IN', 'quantity': 5, 'reason': '',
            })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Quantidade inválida')

    def test_invalid_movement_type_error_shows_inline_error_on_product_update(self):
        with patch('inventory.views.register_movement_service', side_effect=InvalidMovementTypeError('XX')):
            response = self.client.post(self.url, {
                'type': 'IN', 'quantity': 5, 'reason': '',
            })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tipo de movimentação inválido')

    def test_inactive_product_error_shows_inline_error_on_product_update(self):
        with patch('inventory.views.register_movement_service', side_effect=InactiveProductError(self.product)):
            response = self.client.post(self.url, {
                'type': 'IN', 'quantity': 5, 'reason': '',
            })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Produto inativo e sem estoque')



class CrossCompanyIsolationTestCase(TestCase):
    """Covers #44: a user from Company A must not reach Company B's
    product through any object-specific lookup, not just be filtered
    out of listings - including by typing the URL directly (IDOR).
    Every case expects 404, not 403: 403 would confirm the id exists,
    404 treats "wrong company" identically to "never existed".
    """

    def setUp(self):
        self.company_a = Company.objects.create(name='Empresa A')
        self.company_b = Company.objects.create(name='Empresa B')

        self.user_a = User.objects.create_user(username='dono_a', password='senha-teste-123')
        Membership.objects.create(user=self.user_a, company=self.company_a)
        gestor_group = Group.objects.get(name='Gestor')
        self.user_a.groups.add(gestor_group)
        self.client.force_login(self.user_a)

        self.product_b = Product.objects.create(
            company=self.company_b, name='Produto da Empresa B', price=10, minimum_quantity=1
        )
        StockMovement.objects.create(product=self.product_b, type='IN', quantity=5)

    def test_product_detail_of_other_company_is_404(self):
        response = self.client.get(reverse('product_detail', args=[self.product_b.id]))
        self.assertEqual(response.status_code, 404)

    def test_product_update_of_other_company_is_404(self):
        response = self.client.get(reverse('product_update', args=[self.product_b.id]))
        self.assertEqual(response.status_code, 404)

    def test_product_delete_of_other_company_is_404(self):
        response = self.client.get(reverse('product_delete', args=[self.product_b.id]))
        self.assertEqual(response.status_code, 404)

    def test_product_delete_post_of_other_company_is_404_and_does_not_deactivate(self):
        response = self.client.post(reverse('product_delete', args=[self.product_b.id]))
        self.assertEqual(response.status_code, 404)
        self.product_b.refresh_from_db()
        self.assertTrue(self.product_b.active)

    def test_movement_create_of_other_company_is_404(self):
        response = self.client.get(reverse('movement_create', args=[self.product_b.id]))
        self.assertEqual(response.status_code, 404)

    def test_movement_create_post_of_other_company_is_404_and_creates_no_movement(self):
        response = self.client.post(reverse('movement_create', args=[self.product_b.id]), {
            'type': 'IN', 'quantity': 5, 'reason': '',
        })
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.product_b.movements.count(), 1)  # only the one from setUp

    def test_product_list_does_not_show_other_companys_products(self):
        response = self.client.get(reverse('product_list'))
        self.assertNotContains(response, 'Produto da Empresa B')


class EmployeeManagementTestCase(TestCase):
    """Covers #47: Gestor can deactivate/reactivate an employee's login
    (User.is_active, never delete - see employee_toggle_active's
    docstring for why). Three access-control layers are tested:
    Gestor-only (gestor_required), same-company-only (IDOR, same
    reasoning as #44), and no self-deactivation.
    """

    def setUp(self):
        self.company_a = Company.objects.create(name='Empresa A')
        self.company_b = Company.objects.create(name='Empresa B')

        gestor_group = Group.objects.get(name='Gestor')

        self.gestor = User.objects.create_user(username='gestor_a', password='senha-teste-123')
        self.gestor.groups.add(gestor_group)
        self.gestor_membership = Membership.objects.create(user=self.gestor, company=self.company_a)

        self.operador = User.objects.create_user(username='operador_a', password='senha-teste-123')
        self.operador_membership = Membership.objects.create(user=self.operador, company=self.company_a)

        # Funcionário de outra empresa, para os testes de isolamento
        self.other_gestor = User.objects.create_user(username='gestor_b', password='senha-teste-123')
        self.other_gestor.groups.add(gestor_group)
        Membership.objects.create(user=self.other_gestor, company=self.company_b)

        self.other_operador = User.objects.create_user(username='operador_b', password='senha-teste-123')
        self.other_operador_membership = Membership.objects.create(
            user=self.other_operador, company=self.company_b
        )

    # --- acesso restrito ao grupo Gestor ---

    def test_operador_cannot_view_employee_list(self):
        self.client.force_login(self.operador)
        response = self.client.get(reverse('employee_list'))
        self.assertEqual(response.status_code, 403)

    def test_operador_cannot_toggle_employee_active(self):
        self.client.force_login(self.operador)
        response = self.client.post(
            reverse('employee_toggle_active', args=[self.gestor_membership.id])
        )
        self.assertEqual(response.status_code, 403)

    def test_gestor_can_view_employee_list(self):
        self.client.force_login(self.gestor)
        response = self.client.get(reverse('employee_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'operador_a')

    # --- isolamento entre empresas (mesmo raciocínio do #44) ---

    def test_employee_list_does_not_show_other_companys_employees(self):
        self.client.force_login(self.gestor)
        response = self.client.get(reverse('employee_list'))
        self.assertNotContains(response, 'gestor_b')
        self.assertNotContains(response, 'operador_b')

    def test_gestor_cannot_toggle_employee_of_other_company(self):
        self.client.force_login(self.gestor)
        response = self.client.post(
            reverse('employee_toggle_active', args=[self.other_operador_membership.id])
        )
        self.assertEqual(response.status_code, 404)
        self.other_operador.refresh_from_db()
        self.assertTrue(self.other_operador.is_active)

    # --- bloqueio de auto-desativação ---

    def test_gestor_cannot_deactivate_own_access(self):
        self.client.force_login(self.gestor)
        response = self.client.post(
            reverse('employee_toggle_active', args=[self.gestor_membership.id])
        )
        self.assertRedirects(response, reverse('employee_list'))
        self.gestor.refresh_from_db()
        self.assertTrue(self.gestor.is_active)

    # --- toggle funcionando nos dois sentidos ---

    def test_gestor_deactivates_operador(self):
        self.client.force_login(self.gestor)
        response = self.client.post(
            reverse('employee_toggle_active', args=[self.operador_membership.id])
        )
        self.assertRedirects(response, reverse('employee_list'))
        self.operador.refresh_from_db()
        self.assertFalse(self.operador.is_active)

    def test_gestor_reactivates_operador(self):
        self.operador.is_active = False
        self.operador.save(update_fields=['is_active'])

        self.client.force_login(self.gestor)
        response = self.client.post(
            reverse('employee_toggle_active', args=[self.operador_membership.id])
        )
        self.assertRedirects(response, reverse('employee_list'))
        self.operador.refresh_from_db()
        self.assertTrue(self.operador.is_active)

    def test_deactivated_employee_cannot_log_in(self):
        self.operador.is_active = False
        self.operador.save(update_fields=['is_active'])

        # client.login() é um atalho de teste que chama authenticate()
        # sem um request de verdade - incompatível com o AxesBackend,
        # que exige o request pra rastrear tentativas falhas. Por isso
        # postamos direto na view de login, o mesmo caminho que a
        # aplicação usa de verdade.
        response = self.client.post(reverse('login'), {
            'username': 'operador_a', 'password': 'senha-teste-123',
        })
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class CreateEmployeeServiceTestCase(TestCase):
    """Testa create_employee() direto na service layer, sem passar pela
    view - mesmo padrão de RegisterMovementServiceTestCase."""

    def setUp(self):
        self.company = Company.objects.create(name='Empresa Teste')

    def test_creates_user_group_and_membership(self):
        user, temp_password = create_employee(self.company, 'novo_operador', 'Operador')

        self.assertTrue(User.objects.filter(username='novo_operador').exists())
        self.assertTrue(user.groups.filter(name='Operador').exists())
        self.assertEqual(user.membership.company, self.company)
        self.assertTrue(user.membership.must_change_password)
        # a senha retornada precisa ser a senha de verdade do usuário -
        # check_password confirma contra o hash salvo
        self.assertTrue(user.check_password(temp_password))

    def test_generated_passwords_are_not_predictable(self):
        # secrets, não random - duas chamadas não podem gerar a mesma senha
        _, password_1 = create_employee(self.company, 'user1', 'Operador')
        _, password_2 = create_employee(self.company, 'user2', 'Operador')
        self.assertNotEqual(password_1, password_2)


class EmployeeCreateViewTestCase(TestCase):
    """Covers the Gestor-facing "cadastrar funcionário" flow - a
    funcionalidade que faltava (só existiam toggle/desativar, nada
    criava um funcionário novo pelo próprio sistema)."""

    def setUp(self):
        self.company = Company.objects.create(name='Empresa Teste')
        gestor_group = Group.objects.get(name='Gestor')
        self.gestor = User.objects.create_user(username='gestor', password='senha-teste-123')
        self.gestor.groups.add(gestor_group)
        Membership.objects.create(user=self.gestor, company=self.company)
        self.client.force_login(self.gestor)
        self.url = reverse('employee_create')

    def test_operador_cannot_access(self):
        operador = User.objects.create_user(username='operador', password='senha-teste-123')
        Membership.objects.create(user=operador, company=self.company)
        self.client.force_login(operador)

        response = self.client.post(self.url, {'username': 'novo', 'role': 'Operador'})
        self.assertEqual(response.status_code, 403)

    def test_valid_submission_creates_employee_and_shows_password_once(self):
        response = self.client.post(self.url, {'username': 'joana', 'role': 'Gestor'})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'inventory/employee_create_done.html')
        self.assertContains(response, 'joana')

        new_user = User.objects.get(username='joana')
        self.assertTrue(new_user.groups.filter(name='Gestor').exists())
        self.assertEqual(new_user.membership.company, self.company)

    def test_duplicate_username_shows_form_error_and_creates_nothing(self):
        User.objects.create_user(username='joana', password='outra-senha')

        response = self.client.post(self.url, {'username': 'joana', 'role': 'Operador'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Já existe um usuário com esse nome.')
        # continua existindo só o User original, sem Membership associado
        self.assertFalse(Membership.objects.filter(user__username='joana').exists())


class EmployeeResetPasswordTestCase(TestCase):
    """Covers o "esqueci minha senha" sem infraestrutura de e-mail: o
    Gestor reseta a senha do funcionário manualmente."""

    def setUp(self):
        self.company_a = Company.objects.create(name='Empresa A')
        self.company_b = Company.objects.create(name='Empresa B')
        gestor_group = Group.objects.get(name='Gestor')

        self.gestor = User.objects.create_user(username='gestor_a', password='senha-teste-123')
        self.gestor.groups.add(gestor_group)
        self.gestor_membership = Membership.objects.create(user=self.gestor, company=self.company_a)

        self.operador = User.objects.create_user(username='operador_a', password='senha-antiga')
        self.operador_membership = Membership.objects.create(user=self.operador, company=self.company_a)

        other_operador = User.objects.create_user(username='operador_b', password='senha-teste-123')
        self.other_membership = Membership.objects.create(user=other_operador, company=self.company_b)

        self.client.force_login(self.gestor)

    def test_gestor_cannot_reset_own_password_here(self):
        response = self.client.post(
            reverse('employee_reset_password', args=[self.gestor_membership.id])
        )
        self.assertRedirects(response, reverse('employee_list'))

    def test_cannot_reset_password_of_other_companys_employee(self):
        response = self.client.post(
            reverse('employee_reset_password', args=[self.other_membership.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_resets_password_and_forces_change_on_next_login(self):
        response = self.client.post(
            reverse('employee_reset_password', args=[self.operador_membership.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'inventory/employee_create_done.html')

        self.operador.refresh_from_db()
        self.operador_membership.refresh_from_db()
        self.assertFalse(self.operador.check_password('senha-antiga'))
        self.assertTrue(self.operador_membership.must_change_password)


class ForcePasswordChangeMiddlewareTestCase(TestCase):
    """Covers o middleware que obriga troca de senha antes de liberar
    qualquer outra tela, e que a troca bem-sucedida desliga a flag -
    sem isso a pessoa ficaria presa na tela de troca pra sempre."""

    def setUp(self):
        self.company = Company.objects.create(name='Empresa Teste')
        self.user = User.objects.create_user(username='funcionario', password='temp-senha-123')
        self.membership = Membership.objects.create(
            user=self.user, company=self.company, must_change_password=True
        )
        self.client.force_login(self.user)

    def test_redirected_away_from_any_other_page(self):
        response = self.client.get(reverse('product_list'))
        self.assertRedirects(response, reverse('password_change'))

    def test_password_change_and_logout_pages_stay_reachable(self):
        response = self.client.get(reverse('password_change'))
        self.assertEqual(response.status_code, 200)

    def test_successful_password_change_clears_flag_logs_out_and_redirects_to_login(self):
        response = self.client.post(reverse('password_change'), {
            'old_password': 'temp-senha-123',
            'new_password1': 'nova-senha-forte-456',
            'new_password2': 'nova-senha-forte-456',
        })
        self.assertRedirects(response, reverse('login'))

        self.membership.refresh_from_db()
        self.assertFalse(self.membership.must_change_password)

        # a sessão antiga foi encerrada - a mesma senha temporária não
        # funciona mais, e a senha nova sim. client.login() não serve
        # aqui pelo mesmo motivo do teste acima (AxesBackend exige um
        # request de verdade), então postamos na view de login.
        response = self.client.post(reverse('login'), {
            'username': 'funcionario', 'password': 'temp-senha-123',
        })
        self.assertFalse(response.wsgi_request.user.is_authenticated)

        response = self.client.post(reverse('login'), {
            'username': 'funcionario', 'password': 'nova-senha-forte-456',
        })
        self.assertTrue(response.wsgi_request.user.is_authenticated)


class LoginRateLimitTestCase(TestCase):
    """Covers #17 (rate limit): protege o formulário de login contra
    força bruta. Depois de AXES_FAILURE_LIMIT tentativas erradas
    seguidas, a conta fica bloqueada por um tempo - mesmo que a
    próxima tentativa use a senha certa."""

    def setUp(self):
        self.user = User.objects.create_user(username='usuario_teste', password='senha-correta-123')

    def test_account_locked_after_failure_limit_reached(self):
        for _ in range(settings.AXES_FAILURE_LIMIT):
            response = self.client.post(reverse('login'), {
                'username': 'usuario_teste', 'password': 'senha-errada',
            })
            self.assertFalse(response.wsgi_request.user.is_authenticated)

        # mesmo com a senha CERTA, a conta continua bloqueada
        response = self.client.post(reverse('login'), {
            'username': 'usuario_teste', 'password': 'senha-correta-123',
        })
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_still_works_below_failure_limit(self):
        for _ in range(settings.AXES_FAILURE_LIMIT - 1):
            response = self.client.post(reverse('login'), {
                'username': 'usuario_teste', 'password': 'senha-errada',
            })
            self.assertFalse(response.wsgi_request.user.is_authenticated)

        response = self.client.post(reverse('login'), {
            'username': 'usuario_teste', 'password': 'senha-correta-123',
        })
        self.assertTrue(response.wsgi_request.user.is_authenticated)


class ProductReactivationTestCase(TestCase):
    """Covers #29: a Gestor can list and reactivate a soft-deleted
    product. Same three access-control layers as EmployeeManagementTestCase
    (Gestor-only, same-company-only), minus the self-block - a product
    has no "self" to protect.
    """

    def setUp(self):
        self.company_a = Company.objects.create(name='Empresa A')
        self.company_b = Company.objects.create(name='Empresa B')

        gestor_group = Group.objects.get(name='Gestor')

        self.gestor = User.objects.create_user(username='gestor_a', password='senha-teste-123')
        self.gestor.groups.add(gestor_group)
        Membership.objects.create(user=self.gestor, company=self.company_a)

        self.operador = User.objects.create_user(username='operador_a', password='senha-teste-123')
        Membership.objects.create(user=self.operador, company=self.company_a)

        self.inactive_product = Product.objects.create(
            company=self.company_a, name='Produto Inativo', price=10, minimum_quantity=1, active=False
        )
        self.active_product = Product.objects.create(
            company=self.company_a, name='Produto Ativo', price=10, minimum_quantity=1, active=True
        )

        # Produto inativo de outra empresa, para os testes de isolamento
        self.other_inactive_product = Product.objects.create(
            company=self.company_b, name='Produto Inativo da Empresa B', price=10, minimum_quantity=1, active=False
        )

    # --- acesso restrito ao grupo Gestor ---

    def test_operador_cannot_view_inactive_product_list(self):
        self.client.force_login(self.operador)
        response = self.client.get(reverse('product_inactive_list'))
        self.assertEqual(response.status_code, 403)

    def test_operador_cannot_reactivate_product(self):
        self.client.force_login(self.operador)
        response = self.client.post(reverse('product_reactivate', args=[self.inactive_product.id]))
        self.assertEqual(response.status_code, 403)

    def test_gestor_can_view_inactive_product_list(self):
        self.client.force_login(self.gestor)
        response = self.client.get(reverse('product_inactive_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Produto Inativo')

    def test_inactive_product_list_does_not_show_active_products(self):
        self.client.force_login(self.gestor)
        response = self.client.get(reverse('product_inactive_list'))
        self.assertNotContains(response, 'Produto Ativo')

    # --- isolamento entre empresas (mesmo raciocínio do #44) ---

    def test_inactive_product_list_does_not_show_other_companys_products(self):
        self.client.force_login(self.gestor)
        response = self.client.get(reverse('product_inactive_list'))
        self.assertNotContains(response, 'Produto Inativo da Empresa B')

    def test_gestor_cannot_reactivate_product_of_other_company(self):
        self.client.force_login(self.gestor)
        response = self.client.post(
            reverse('product_reactivate', args=[self.other_inactive_product.id])
        )
        self.assertEqual(response.status_code, 404)
        self.other_inactive_product.refresh_from_db()
        self.assertFalse(self.other_inactive_product.active)

    # --- reativação em si ---

    def test_gestor_reactivates_product(self):
        self.client.force_login(self.gestor)
        response = self.client.post(reverse('product_reactivate', args=[self.inactive_product.id]))
        self.assertRedirects(response, reverse('product_inactive_list'))
        self.inactive_product.refresh_from_db()
        self.assertTrue(self.inactive_product.active)

    def test_reactivated_product_appears_in_regular_listing(self):
        self.client.force_login(self.gestor)
        self.client.post(reverse('product_reactivate', args=[self.inactive_product.id]))

        response = self.client.get(reverse('product_list'))
        self.assertContains(response, 'Produto Inativo')


class DashboardViewTestCase(TestCase):
    """Covers as duas métricas do dashboard que são regra de negócio de
    verdade (não só visualização): o valor total em estoque precisa
    bater a conta certa, e "produtos críticos" precisa listar só quem
    está abaixo do próprio mínimo - de uma única empresa."""

    def setUp(self):
        self.company = Company.objects.create(name='Empresa Teste')
        self.other_company = Company.objects.create(name='Outra Empresa')

        self.user = User.objects.create_user(username='funcionario', password='senha-teste-123')
        Membership.objects.create(user=self.user, company=self.company)

        self.product_ok = Product.objects.create(
            company=self.company, name='Produto OK', price=10, minimum_quantity=5
        )
        StockMovement.objects.create(product=self.product_ok, type='IN', quantity=20)

        self.product_critico = Product.objects.create(
            company=self.company, name='Produto Crítico', price=Decimal('2.50'), minimum_quantity=10
        )
        StockMovement.objects.create(product=self.product_critico, type='IN', quantity=3)

        # produto e movimentação de outra empresa - não deve entrar em
        # nenhuma das contas acima
        other_product = Product.objects.create(
            company=self.other_company, name='Produto de Outra Empresa', price=100, minimum_quantity=0
        )
        StockMovement.objects.create(product=other_product, type='IN', quantity=50)

    def test_total_stock_value_is_calculated_correctly(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        # 20 * 10 + 3 * 2.50 = 207.50 - não inclui os 50 * 100 da outra empresa
        self.assertEqual(response.context['total_value'], Decimal('207.50'))

    def test_only_products_below_minimum_are_listed_as_critical(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(list(response.context['critical_products']), [self.product_critico])

    def test_movement_count_reflects_only_this_companys_movements(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['movement_count'], 2)


class CreateSuperuserIfNoneExistsCommandTestCase(TestCase):
    """Covers o management command usado no build do Render (tier
    gratuito não tem Shell pra rodar createsuperuser manualmente) -
    precisa criar o superusuário na primeira vez, mas nunca tentar de
    novo (ou dar erro) nos deploys seguintes, quando ele já existe."""

    def test_creates_superuser_when_none_exists_and_env_vars_are_set(self):
        with patch.dict('os.environ', {
            'DJANGO_SUPERUSER_USERNAME': 'admin_producao',
            'DJANGO_SUPERUSER_PASSWORD': 'senha-forte-de-producao-123',
        }):
            call_command('create_superuser_if_none_exists')

        user = User.objects.get(username='admin_producao')
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password('senha-forte-de-producao-123'))

    def test_does_nothing_when_a_superuser_already_exists(self):
        User.objects.create_superuser(username='ja_existe', password='qualquer-senha-123')

        with patch.dict('os.environ', {
            'DJANGO_SUPERUSER_USERNAME': 'outro_admin',
            'DJANGO_SUPERUSER_PASSWORD': 'outra-senha-123',
        }):
            call_command('create_superuser_if_none_exists')

        # não criou o segundo, nem quebrou tentando
        self.assertFalse(User.objects.filter(username='outro_admin').exists())
        self.assertEqual(User.objects.filter(is_superuser=True).count(), 1)

    def test_does_nothing_when_env_vars_are_missing(self):
        with patch.dict('os.environ', {}, clear=False):
            os.environ.pop('DJANGO_SUPERUSER_USERNAME', None)
            os.environ.pop('DJANGO_SUPERUSER_PASSWORD', None)
            call_command('create_superuser_if_none_exists')

        self.assertFalse(User.objects.filter(is_superuser=True).exists())