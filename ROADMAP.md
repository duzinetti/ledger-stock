# Roadmap Técnico - Realinhado com o PRD

Este roadmap foi reorganizado depois do PRD (ver `PRD.md`). A mudança
principal: as fases antigas eram organizadas por **camada técnica**
(banco, estilo, dashboard, API...). Agora estão organizadas por
**prioridade de produto** (MVP → V2 → Later), porque o PRD definiu que
"pronto" significa "deployado e usável por um comércio real", não
"todas as camadas técnicas implementadas".

**Status dos dois bloqueios que existiam aqui:** ambos resolvidos.

> ✅ **Bloqueio 1 — Multi-tenancy (Questão Aberta #1 do PRD).**
> Resolvido a favor de "nasce multi-tenant desde já". Implementado
> nesta sessão (`Company`, `Membership`, `Product.company`, isolamento
> por empresa em todo lookup, papéis Gestor/Operador) — ver PRD.md
> §10 e o histórico de PRs (`#17`, `#44`-`#47`, `#29`).

> ✅ **Bloqueio 2 — Soft delete vs. exclusão física (Questão Aberta #2
> do PRD).** Resolvido em 2026-08-19: soft delete via `Product.active`.
> Listagem e reativação de inativos (que faltava desde a resolução
> original) implementada em `#29`.

---

## MVP — "deployado e usável por um comércio real"

Alinhado à Seção 5 do PRD. Critério de corte: o dono confia no número
de estoque, o funcionário opera sem fricção, com segurança básica.

### MVP.1 — Funcional (status: quase concluído)
- [x] CRUD completo de produto (criar, editar, ver, excluir)
- [x] Movimentação de estoque com bloqueio de saída maior que o
      disponível
- [x] Concorrência segura (`select_for_update`, sem race condition)
- [x] N+1 corrigido na listagem
- [x] Paginação e busca por nome
- [x] **Validação via `ModelForm`** (preço > 0, quantidade > 0,
      nome obrigatório) — `ProductForm`/`MovementForm`, com
      `clean_price` cobrindo a regra de negócio (PRD §6.1)
- [ ] **Categoria como texto livre, aceito como dívida do MVP**
      (PRD 6.1) — decisão já em vigor (não é um "falta fazer", é a
      escolha atual); vira catálogo estruturado só no V2
- [x] Decisão de exclusão física vs. soft delete (Bloqueio 2) aplicada
      no model — `Product.active`, com listagem/reativação (`#29`)

### MVP.2 — Banco de dados de produção
- [ ] PostgreSQL configurado (SQLite não serve para acesso concorrente
      real, conforme discutido) — decisão registrada em PRD.md §10:
      Render (hosting) + Neon (Postgres gerenciado)
- [ ] Variáveis de ambiente via `python-decouple` (`SECRET_KEY` ainda
      hardcoded em `settings.py`, `DEBUG=True` fixo)
- [x] `empresa_id` no schema — `Company`, `Membership`,
      `Product.company`, isolamento por empresa em todo lookup (`#17`,
      `#44`)

### MVP.3 — Autenticação (versão mínima, não a Fase 5 completa)
- [x] Login/logout
- [x] Login obrigatório para **todas** as ações (PRD 6.4)
- [x] Toda movimentação associa o usuário autenticado
- [x] Senha com hashing padrão do Django (comportamento padrão,
      nenhuma implementação própria necessária)
- [x] Papéis diferenciados (Operador/Gestor) — adiantado do V2 junto
      com o pacote de multi-tenancy (`#45`, `#47`, `#29`), não ficou
      pra depois do MVP como o plano original previa

### MVP.4 — Alerta de estoque baixo na interface
- [x] Já implementado (property `estoque_baixo`, exibido na listagem)

### MVP.5 — Deploy
- [ ] HTTPS obrigatório, variáveis sensíveis fora do código
- [ ] Deploy público (Railway, Render ou PythonAnywhere)
- [ ] Checklist de segurança mínima revisado antes de publicar:
      `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`,
      `CSRF_COOKIE_SECURE`

**Critério de conclusão do MVP:** um comércio real consegue cadastrar
produtos, registrar movimentações com segurança, ver alerta de
estoque baixo, com login obrigatório, rodando num link público com
HTTPS.

---

## V2 — evolução direta pós-MVP

Alinhado à Seção 5 do PRD. Só começa depois do MVP estar deployado —
o PRD é explícito que "done" é o MVP no ar, não tudo isso completo.

- [ ] Dashboard com métricas agregadas (valor total, produtos
      críticos, gráfico de movimentação) — reaproveitando
      `with_current_quantity()` para não reintroduzir N+1
- [x] Permissões por papel: `Group` Operador vs. Gestor — adiantado
      pro pacote de multi-tenancy, ver MVP.3
- [ ] Categoria estruturada (migrar de texto livre para model
      `Categoria`, corrigindo a dívida assumida no MVP)
- [ ] Movimentação: campo `is_sale` (boolean, default `True`) +
      `unit_price` congelado no momento da movimentação, para viabilizar
      relatório de vendas por período (`#51`) — decisão registrada:
      **não** estruturar `motivo` em categorias, ver `#51`
- [ ] API REST (DRF + JWT), reaproveitando o `services.py` já existente
- [ ] Exportação de relatório (CSV/PDF)
- [ ] Reskin do admin (`django-jazzmin`) e estilização geral
      (Bootstrap/Tailwind)

---

## Later — visão de produto, sem compromisso de prazo

Alinhado à Seção 5 do PRD.

- [ ] Gestão de fornecedores e pedido de compra
- [ ] Integração com PDV / marketplace
- [ ] Previsão de demanda / sugestão de reposição (com ou sem IA —
      Fase 8 do roadmap anterior, mantida aqui)
- [ ] 2FA (`django-otp`), auditoria avançada (`django-simple-history`),
      rate limiting no login (`django-axes`) — segurança de nível
      empresarial, relevante quando houver múltiplos clientes reais
- [ ] App mobile nativo

---

## O que muda em relação ao roadmap técnico anterior

| Antes | Agora |
|---|---|
| Fases sequenciais por camada técnica (banco → estilo → dashboard → auth → API → deploy) | Fases por prioridade de produto (MVP → V2 → Later) |
| Deploy era a Fase 7, quase no final | Deploy é parte do MVP — "done" é estar no ar, não ter todas as camadas prontas |
| Autenticação completa com papéis era um bloco único (Fase 5) | Dividida: login básico obrigatório entra no MVP; papéis diferenciados (Operador/Gestor) viram V2 |
| Dashboard e API eram fases centrais do meio do roadmap | Viram V2 — importantes, mas não bloqueiam o "usável por um comércio real" |
| Multi-tenancy não era mencionado | Vira decisão explícita a ser tomada **antes** do MVP.2 (banco de dados), não depois |
| Segurança avançada (2FA, auditoria, rate limiting) misturada com autenticação básica | Separada para Later — nível empresarial, não essencial pro primeiro comércio real usando o sistema |

---

## Bibliotecas por bloco

| Biblioteca | Bloco | Uso |
|---|---|---|
| Django | MVP.1 | Framework principal |
| python-decouple | MVP.2 | Variáveis de ambiente |
| mysqlclient / psycopg2 | MVP.2 | Driver do banco de produção |
| gunicorn / whitenoise | MVP.5 | Deploy |
| django-crispy-forms, Bootstrap | V2 | Estilização |
| django-jazzmin | V2 | Reskin do admin |
| Chart.js | V2 | Gráficos do dashboard |
| djangorestframework + simplejwt + drf-spectacular | V2 | API |
| django-otp | Later | 2FA |
| django-simple-history | Later | Auditoria avançada |
| django-axes | Later | Rate limiting no login |
| anthropic (SDK) | Later | Integração com IA |
| redis, celery | Later | Escalabilidade sob tráfego real |

---

## Próxima ação recomendada

Os dois bloqueios estão resolvidos e o MVP está mais avançado do que
esta seção sugeria antes da atualização de 2026-09-04 — falta
essencialmente MVP.2 (Postgres/Neon + `python-decouple`, substituindo
`SECRET_KEY`/`DEBUG` hardcoded) e MVP.5 (deploy: HTTPS, Render,
checklist de segurança mínima). Com isso, o MVP fecha.
