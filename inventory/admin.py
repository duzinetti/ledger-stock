from django.contrib import admin
from .models import Product, StockMovement


# Exposes Product in /admin so the owner (Marcos, PRD persona) can
# inspect and fix data directly without a dedicated internal tool -
# there is no MVP requirement for an admin-facing UI beyond Django's.
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'current_quantity', 'minimum_quantity', 'low_stock')
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
@admin.register(StockMovement)
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
