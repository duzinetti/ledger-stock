# Roadmap - Gerenciador de Estoque (Django)

Ordem sugerida de desenvolvimento, do esqueleto atual até uma versão
completa com dashboard e API.

---

## Fase 0 — Base (já feita)
- [x] Estrutura do projeto Django (`estoque_project` + app `estoque`)
- [x] Models `Produto` e `Movimentacao`
- [x] Django Admin registrado
- [x] Views funcionais (listar, cadastrar, detalhe, movimentação)
- [x] Templates simples sem estilo
- [x] Migrations validadas (SQLite)

---

## Fase 1 — Consolidar o funcional
Objetivo: garantir que a lógica de negócio está sólida antes de qualquer
estilização.

- [ ] Editar e remover produto (view + template)
- [ ] Validações de formulário (preço não pode ser negativo, nome obrigatório etc.)
- [ ] Confirmação antes de excluir produto
- [ ] Paginação na listagem de produtos
- [ ] Testes unitários básicos com `unittest`/`pytest-django` para:
  - cálculo de `quantidade_atual`
  - bloqueio de saída maior que o estoque disponível
  - `estoque_baixo`

## Fase 2 — Banco de dados
Objetivo: sair do SQLite e deixar o projeto "pronto para produção".

- [ ] Configurar MySQL ou PostgreSQL localmente
- [ ] Trocar `DATABASES` no `settings.py` (usar variáveis de ambiente com `python-decouple` ou `django-environ`, nunca senha hardcoded)
- [ ] Rodar `migrate` no novo banco e validar que os dados batem
- [ ] Adicionar índices em campos usados em busca/filtro (`nome`, `categoria`)
- [ ] Revisar `related_name` e `on_delete` das FKs conforme o sistema cresce (ex: fornecedores)

## Fase 3 — Estilização
Objetivo: deixar a interface apresentável para portfólio.

- [ ] Adicionar Bootstrap (ou Tailwind) via CDN no `base.html`
- [ ] Estilizar tabelas, formulários e botões
- [ ] `django-crispy-forms` para formulários mais limpos (opcional)
- [ ] Layout responsivo básico (funciona em mobile)

## Fase 4 — Dashboard do administrador
Objetivo: ir além do CRUD simples e mostrar análise de dados.

- [ ] Reskin rápido do Django Admin nativo com `django-jazzmin`
- [ ] View de dashboard customizada com:
  - total de produtos cadastrados
  - lista de produtos com estoque baixo
  - valor total em estoque (soma de `preco * quantidade_atual`)
  - gráfico de entradas x saídas (Chart.js alimentado pela view)
- [ ] Filtro de período nas movimentações (últimos 7/30 dias)

## Fase 5 — Autenticação e permissões
Objetivo: sistema pronto para múltiplos usuários.

- [ ] Login/logout (`django.contrib.auth`)
- [ ] Restringir cadastro/edição a usuários autenticados
- [ ] Diferenciar perfis (ex: operador só registra movimentação, gestor edita produtos)
- [ ] Registrar qual usuário fez cada movimentação (campo `usuario` em `Movimentacao`)

## Fase 6 — API (Django REST Framework)
Objetivo: expor os dados para consumo externo (ex: um app mobile, ou integração futura).

- [ ] Instalar e configurar `djangorestframework`
- [ ] Serializers para `Produto` e `Movimentacao`
- [ ] Endpoints REST:
  - `GET /api/produtos/` — listar
  - `POST /api/produtos/` — criar
  - `GET /api/produtos/<id>/` — detalhe
  - `POST /api/produtos/<id>/movimentacao/` — registrar movimentação
- [ ] Autenticação da API (Token ou JWT via `djangorestframework-simplejwt`)
- [ ] Documentação automática da API (`drf-spectacular` ou `drf-yasg`, gera Swagger/OpenAPI)

## Fase 7 — Deploy (opcional, mas valoriza o portfólio)
- [ ] Variáveis de ambiente para produção (`DEBUG=False`, `SECRET_KEY` fora do código)
- [ ] `collectstatic` configurado
- [ ] Deploy em plataforma gratuita (Railway, Render ou PythonAnywhere)
- [ ] README com instruções de instalação e link do projeto rodando

---

## Bibliotecas mencionadas ao longo do roadmap

| Biblioteca                        | Uso                                          |
|-----------------------------------|-----------------------------------------------|
| Django                            | Framework principal                           |
| djangorestframework               | API REST                                      |
| djangorestframework-simplejwt     | Autenticação JWT na API                       |
| drf-spectacular                   | Documentação automática da API (Swagger)      |
| django-jazzmin                    | Reskin do Django Admin                        |
| django-crispy-forms               | Estilização de formulários                    |
| python-decouple / django-environ  | Variáveis de ambiente (segredos fora do código)|
| pytest-django                     | Testes automatizados                          |
| Chart.js                          | Gráficos no dashboard (via template)          |

---

## Observação sobre ordem

Cada fase pressupõe a anterior concluída, mas a Fase 2 (banco de dados)
pode ser adiada e feita em paralelo com a Fase 3/4 — não é bloqueante,
já que o SQLite funciona bem para desenvolvimento e até para portfólio.
O que **não** vale a pena inverter é: funcional antes de bonito (Fase 1
antes da Fase 3), e autenticação antes de API (Fase 5 antes da Fase 6),
já que a API vai precisar reaproveitar a lógica de permissões.
