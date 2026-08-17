from django.contrib import admin
from .models import Product, StockMovement


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'current_quantity', 'minimum_quantity', 'low_stock')
    search_fields = ('name', 'category')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'type', 'quantity', 'date', 'reason', 'user')
    list_filter = ('type', 'date')
    # select_related avoids an extra query per row when showing product/user
    list_select_related = ('product', 'user')
