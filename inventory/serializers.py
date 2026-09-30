from rest_framework import serializers

from .models import MovementType, Product, StockMovement


class ProductSerializer(serializers.ModelSerializer):
    # current_quantity é uma property calculada (soma das movimentações),
    # não uma coluna - SerializerMethodField expõe ela como se fosse um
    # campo normal na resposta, sem deixar escrever nela.
    current_quantity = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'price', 'minimum_quantity',
            'current_quantity', 'active',
        ]
        # company nunca é aceito do cliente - é sempre atribuído pelo
        # ProductViewSet a partir da empresa de quem está autenticado,
        # senão um chamador poderia criar produto pra empresa alheia.
        read_only_fields = ['active']

    def get_current_quantity(self, obj):
        return obj.current_quantity


class StockMovementSerializer(serializers.ModelSerializer):
    """Representação de leitura - criação passa por
    StockMovementCreateSerializer + services.register_movement(),
    nunca direto por aqui (ver api_views.StockMovementViewSet)."""

    class Meta:
        model = StockMovement
        fields = [
            'id', 'product', 'type', 'quantity', 'date', 'reason',
            'user', 'is_sale', 'unit_price',
        ]
        read_only_fields = fields


class StockMovementCreateSerializer(serializers.Serializer):
    """Só valida o FORMATO do dado de entrada (tipo/obrigatoriedade) -
    a regra de negócio (estoque suficiente, produto ativo, trava de
    concorrência) continua inteiramente em services.register_movement(),
    chamado pela view. Um ModelSerializer padrão criaria o
    StockMovement direto via .save(), o que ignoraria a trava e a
    validação - o mesmo motivo pelo qual o admin não pode criar
    movimentação direto (ver StockMovementAdmin)."""

    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    type = serializers.ChoiceField(choices=MovementType.choices)
    quantity = serializers.IntegerField()
    reason = serializers.CharField(required=False, allow_blank=True, default='')
    is_sale = serializers.BooleanField(required=False, default=True)
