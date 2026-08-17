# Roadmap Técnico - Realinhado com o PRD

Este roadmap foi reorganizado depois do PRD (ver `PRD.md`). A mudança
principal: as fases antigas eram organizadas por **camada técnica**
(banco, estilo, dashboard, API...). Agora estão organizadas por
**prioridade de produto** (MVP → V2 → Later), porque o PRD definiu que
"pronto" significa "deployado e usável por um comércio real", não
"todas as camadas técnicas implementadas".

**Antes de tudo:** duas Questões Abertas do PRD **bloqueiam** o início
do MVP e precisam de decisão sua antes de eu continuar implementando:

> ⚠️ **Bloqueio 1 — Multi-tenancy (Questão Aberta #1 do PRD).**
> Se a resposta de longo prazo é "sim, eventualmente", o campo
> `empresa_id` deveria entrar no `Produto` e no model de usuário
> **agora**, na Fase MVP, não depois. Migrar dados reais de
> single-tenant para multi-tenant depois é caro e arriscado. Preciso
> que você decida: (a) nasce multi-tenant desde já (mais trabalho
> agora, path limpo depois), ou (b) fica single-tenant no MVP e
> multi-tenant vira reescrita reconhecida como dívida técnica
> deliberada em "Later".

> ⚠️ **Bloqueio 2 — Soft delete vs. exclusão física (Questão Aberta #2
> do PRD).** Afeta o model `Produto` (campo `ativo`) e toda query que
> lista produtos. Fácil de decidir agora, caro de mudar depois de
> haver dados reais de exclusão no ar.

Sem resposta a essas duas, vou seguir com as premissas que já assumi
no PRD (single-tenant por ora, exclusão física por ora) — mas isso é
dívida técnica **documentada**, não esquecida.

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
- [ ] **Validação via `ModelForm`** (preço > 0, quantidade > 0,
      nome obrigatório) — hoje ainda lê `request.POST` direto
- [ ] **Categoria como texto livre, aceito como dívida do MVP**
      (PRD 6.1) — não vira `select` estruturado nesta fase
- [ ] Decisão de exclusão física vs. soft delete (Bloqueio 2) aplicada
      no model antes de seguir

### MVP.2 — Banco de dados de produção
- [ ] MySQL ou PostgreSQL configurado (SQLite não serve para acesso
      concorrente real, conforme discutido)
- [ ] Variáveis de ambiente via `python-decouple`
- [ ] Se Bloqueio 1 for resolvido a favor de multi-tenant: `empresa_id`
      entra no schema **nesta fase**, antes de qualquer dado real
      existir

### MVP.3 — Autenticação (versão mínima, não a Fase 5 completa)
O PRD reduz a autenticação do MVP ao essencial — papéis
diferenciados (Operador/Gestor) ficam para V2, não MVP:
- [ ] Login/logout
- [ ] Login obrigatório para **todas** as ações (PRD 6.4 — a
      recomendação registrada foi login obrigatório em tudo, inclusive
      visualização, para um sistema comercial real, não só escrita)
- [ ] Toda movimentação associa o usuário autenticado (campo já existe
      no model, falta aplicar a checagem)
- [ ] Senha com hashing padrão do Django (já é o comportamento padrão,
      só precisa ser validado, não implementado do zero)

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
      `com_quantidade_atual()` para não reintroduzir N+1
- [ ] Permissões por papel: `Group` Operador vs. Gestor
- [ ] Categoria estruturada (migrar de texto livre para model
      `Categoria`, corrigindo a dívida assumida no MVP)
- [ ] Motivo de movimentação estruturado (enum: Venda, Devolução,
      Perda, Ajuste — em vez de texto livre, conforme PRD 6.2)
- [ ] API REST (DRF + JWT), reaproveitando o `services.py` já existente
- [ ] Exportação de relatório (CSV/PDF)
- [ ] Reskin do admin (`django-jazzmin`) e estilização geral
      (Bootstrap/Tailwind)

---

## Later — visão de produto, sem compromisso de prazo

Alinhado à Seção 5 do PRD.

- [ ] Multi-tenancy completo, se não resolvido no Bloqueio 1 do MVP
- [ ] Gestão de fornecedores e pedido de compra
- [ ] Integração com PDV / marketplace
- [ ] Previsão de demanda / sugestão de reposição (com ou sem IA —
      Fase 8 do roadmap anterior, mantida aqui)
- [ ] 2FA (`django-otp`), auditoria avançada (`django-simple-history`),
      rate limiting no login (`django-axes`) — seguran��a de nível
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

Responder os dois bloqueios (multi-tenancy e soft delete) antes de eu
seguir implementando o MVP.2 (banco de dados) — são os dois pontos do
PRD que mudam o schema, e schema é caro de corrigir depois de existir
dado real no banco.
