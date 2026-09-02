from django.contrib import admin
from .models import Product, StockMovement
from .forms import ProductForm
from django.contrib.admin import AdminSite
from django.contrib.auth.models import User, Group


# Exposes Product in /admin so the owner (Marcos, PRD persona) can
# inspect and fix data directly without a dedicated internal tool -
# there is no MVP requirement for an admin-facing UI beyond Django's.

class RestrictedAdminSite(AdminSite):
    def has_permission(self, request):
        return request.user.is_active and request.user.is_staff and request.user.is_superuser


admin_site = RestrictedAdminSite()


class ProductAdmin(admin.ModelAdmin):
    form = ProductForm

    def get_queryset(self, request):
            qs = super().get_queryset(request)
            return qs.with_current_quantity()

    @admin.display(description='Quantidade')
    def current_quantity_display(self, obj):
         return obj.current_qty

    @admin.display(description='Estoque baixo', boolean=True)
    def low_stock_display(self, obj):
        return obj.is_low_stock

    list_display = ('name', 'category', 'price', 'current_quantity_display', 'minimum_quantity', 'low_stock_display', 'active')
    list_filter = ('active',)
    search_fields = ('name', 'category')


# Movement history needs to be auditable from admin too (PRD §3 goal:
# "histórico auditável"), so type/date are filterable and product/user
# are shown without triggering N+1 (see list_select_related below).
#
# Read-only by design: the default ModelAdmin would let any staff user
# add, edit, or delete a StockMovement directly through the ORM, which
# both lets someone silently rewrite the audit trail and skips
# services.register_movement()'s locked, insufficient-stock-safe write
# path entirely (the admin's auto-generated add form talks straight to
# the ORM). New movements must go through the movement_create view, the
# one path that keeps the ledger append-only and stock-safe.
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'type', 'quantity', 'date', 'reason', 'user')
    list_filter = ('type', 'date')
    # select_related avoids an extra query per row when showing product/user
    list_select_related = ('product', 'user')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin_site.register(Product, ProductAdmin)
admin_site.register(StockMovement, StockMovementAdmin)
admin_site.register(User)
admin_site.register(Group)
