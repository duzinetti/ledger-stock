from rest_framework import status, viewsets
from rest_framework.response import Response

from .models import Product, StockMovement
from .serializers import (
    ProductSerializer,
    StockMovementCreateSerializer,
    StockMovementSerializer,
)
from .services import (
    InactiveProductError,
    InsufficientStockError,
    InvalidMovementTypeError,
    InvalidQuantityError,
    register_movement,
)


class ProductViewSet(viewsets.ModelViewSet):
    """CRUD de produtos, sempre restrito à empresa de quem chama -
    mesmo padrão de isolamento das views normais (get_object_or_404
    filtrado por company), só que aqui é o próprio queryset que já
    nasce filtrado. Sem DELETE: o app nunca apaga produto de verdade,
    só inativa (product_delete) - a API ainda não tem essa ação, fica
    pra depois se algum consumidor precisar.
    """
    serializer_class = ProductSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        return Product.objects.filter(company=self.request.user.membership.company)

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.membership.company)


class StockMovementViewSet(viewsets.ModelViewSet):
    """Leitura normal do histórico + criação obrigatoriamente via
    services.register_movement() (nunca serializer.save() direto) -
    é a mesma trava/validação que a tela normal usa, e o motivo de
    existir camada de serviço: qualquer chamador novo (aqui, a API)
    reusa a regra em vez de reimplementar. Sem PATCH/DELETE: uma
    movimentação já registrada é histórico, não se edita (mesma regra
    do StockMovementAdmin, que é somente leitura depois de criado).
    """
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        return StockMovement.objects.filter(
            product__company=self.request.user.membership.company
        ).select_related('product', 'user')

    def get_serializer_class(self):
        if self.action == 'create':
            return StockMovementCreateSerializer
        return StockMovementSerializer

    def create(self, request, *args, **kwargs):
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data

        product = data['product']
        if product.company_id != request.user.membership.company_id:
            # Mesmo tratamento de "não existe" que o resto do app dá
            # pra objeto de outra empresa (IDOR) - 404, não 403, pra
            # não confirmar que o ID existe.
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            movement = register_movement(
                product_id=product.id,
                movement_type=data['type'],
                quantity=data['quantity'],
                reason=data.get('reason', ''),
                user=request.user,
                is_sale=data.get('is_sale', True),
            )
        except (InsufficientStockError, InvalidQuantityError,
                InvalidMovementTypeError, InactiveProductError) as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        output_serializer = StockMovementSerializer(movement)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
