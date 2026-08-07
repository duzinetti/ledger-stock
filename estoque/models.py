from django.db import models
from django.db.models import Sum, Case, When, IntegerField


class Produto(models.Model):
    nome = models.CharField(max_length=100)
    categoria = models.CharField(max_length=50, blank=True)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade_minima = models.IntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

    @property
    def quantidade_atual(self):
        """Calcula a quantidade em estoque a partir do histórico de movimentações."""
        resultado = self.movimentacoes.aggregate(
            total=Sum(
                Case(
                    When(tipo=Movimentacao.ENTRADA, then='quantidade'),
                    When(tipo=Movimentacao.SAIDA, then=-1 * models.F('quantidade')),
                    output_field=IntegerField(),
                )
            )
        )
        return resultado['total'] or 0

    @property
    def estoque_baixo(self):
        return self.quantidade_atual < self.quantidade_minima


class Movimentacao(models.Model):
    ENTRADA = 'E'
    SAIDA = 'S'
    TIPO_CHOICES = [
        (ENTRADA, 'Entrada'),
        (SAIDA, 'Saída'),
    ]

    produto = models.ForeignKey(
        Produto, on_delete=models.CASCADE, related_name='movimentacoes'
    )
    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
    quantidade = models.IntegerField()
    data = models.DateTimeField(auto_now_add=True)
    motivo = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.produto.nome} ({self.quantidade})'
