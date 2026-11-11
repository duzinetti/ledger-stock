from django.db import migrations

# Função + trigger que bloqueiam UPDATE/DELETE direto na tabela de
# StockMovement, no próprio banco - não apenas no Django. Isso cobre
# qualquer forma de escrita (shell, psql, uma futura integração) que
# bypasse a camada de serviço/admin/API, que já bloqueiam isso em
# Python mas só protegem quem passa por ali.
CREATE_TRIGGER_SQL = """
    CREATE OR REPLACE FUNCTION prevent_stockmovement_mutation()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION
            'StockMovement é um registro histórico imutável - % não é permitido (id=%)',
            TG_OP, OLD.id;
    END;
    $$ LANGUAGE plpgsql;

    CREATE TRIGGER stockmovement_immutable_trigger
    BEFORE UPDATE OR DELETE ON inventory_stockmovement
    FOR EACH ROW EXECUTE FUNCTION prevent_stockmovement_mutation();
"""

DROP_TRIGGER_SQL = """
    DROP TRIGGER IF EXISTS stockmovement_immutable_trigger ON inventory_stockmovement;
    DROP FUNCTION IF EXISTS prevent_stockmovement_mutation();
"""


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0016_stockmovement_stockmovement_is_sale_only_on_out'),
    ]

    operations = [
        migrations.RunSQL(sql=CREATE_TRIGGER_SQL, reverse_sql=DROP_TRIGGER_SQL),
    ]
