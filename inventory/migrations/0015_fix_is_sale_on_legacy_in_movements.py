# Generated manually - fixes a real bug introduced by migration 0013.

from django.db import migrations


def fix_is_sale_on_legacy_in_movements(apps, schema_editor):
    """0013 added is_sale with default=True and applied that default to
    every row that already existed, including Entradas registered
    before the field existed. "Entrada nunca é venda" (enforced in
    services.register_movement) only applies to movements created
    *after* that migration - it never corrected the historical rows,
    so old Entradas were showing up as sales in the sales report.
    """
    StockMovement = apps.get_model('inventory', 'StockMovement')
    StockMovement.objects.filter(type='IN', is_sale=True).update(is_sale=False)


def reverse_fix_is_sale_on_legacy_in_movements(apps, schema_editor):
    """Not reversible in a meaningful way - which Entradas were wrongly
    True before this migration ran can't be recovered. Reversing just
    leaves is_sale as False (the correct value), a no-op."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0014_populate_unit_price'),
    ]

    operations = [
        migrations.RunPython(
            fix_is_sale_on_legacy_in_movements,
            reverse_fix_is_sale_on_legacy_in_movements,
        ),
    ]
