# PRD — Sistema de Gerenciamento de Estoque para Pequeno Comércio

**Autor:** Eduardo Zinetti (Dudu) | **Documento preparado como exercício de Product Management**
**Status:** Draft v1
**Última atualização:** 2026-08-21

---

## 0. Premissas assumidas (flagged, não inventadas silenciosamente)

Antes do PRD em si, deixo explícito o que assumi para poder avançar, já
que você delegou algumas decisões:

- **MVP definido por mim (pergunta 2):** delimitei o MVP como CRUD de
  produtos + movimentação de estoque com concorrência segura +
  autenticação básica + deploy. Justificativa no item 5.
- **Multi-tenancy (pergunta 3) foi a decisão arquitetural mais crítica
  deste documento** — ver Seção 10, Questão Aberta #1 (resolvida em
  2026-08-21). Na época deste documento você havia respondido
  "eventualmente", o que não era uma resposta neutra: decidir agora
  vs. depois muda o data model desde o dia 1 — por isso foi tratada
  como requisito não resolvido até a decisão formal.
- **Stack (pergunta 4):** assumo Django + MySQL/PostgreSQL + deploy em
  PaaS gratuito, por ser a stack já em desenvolvimento nas conversas
  anteriores. Se isso não for fixo, a Seção 6 muda.
- **"Comércio local"** interpretado como: uma loja física ou pequeno
  atacado com 1 a ~5 funcionários, catálogo entre 50 e 5.000 SKUs,
  sem TI dedicada.

---

## 1. Problem Statement

Pequenos comércios locais (lojas de bairro, pequenos atacados,
oficinas com peças) hoje controlam estoque de três formas ruins:
**caderno físico, planilha Excel/Google Sheets solta, ou "de
memória"**. Isso gera três dores concretas e recorrentes:

1. **Estoque fantasma** — o sistema (ou a cabeça do dono) diz que tem
   produto, mas não tem. Cliente vem, produto não existe, venda
   perdida e experiência ruim.
2. **Falta de rastreabilidade** — quando confere fisicamente e o
   número não bate, ninguém sabe se foi erro de contagem, furto, ou
   venda não registrada. Não existe histórico auditável de quem tirou
   o quê e quando.
3. **Decisão de compra no escuro** — o dono não sabe, de forma
   confiável, quais produtos giram rápido e quais estão parados,
   então reabastece por instinto, empatando capital em itens errados.

Quem sente essa dor primeiro é o **dono/gestor do negócio**, mas quem
sofre o atrito no dia a dia é o **funcionário de balcão/estoque**, que
precisa registrar movimentações rápido, sem fricção, ou simplesmente
para de usar o sistema e volta pro caderno.

---

## 2. Target User + 2 Personas

**Perfil geral:** donos e funcionários de comércio local de pequeno
porte, com letramento digital básico a intermediário — usam WhatsApp,
Excel simples, mas não são technical. Orçamento de software é baixo
ou zero (concorrem mentalmente com "não pagar nada" / planilha).

### Persona 1 — Marcos, o dono/gestor
- 45 anos, dono de uma loja de material de construção com 2
  funcionários
- Usa o celular mais que o computador; abre o sistema no fim do dia
  pra "ver como estão as coisas"
- Dor principal: não confia nos números de estoque, então compra
  "por segurança" e capital fica empatado
- O que ele valoriza: ver rápido o que está acabando, sem precisar
  interpretar planilha ou gráfico complexo
- Frustração com ferramentas atuais: já tentou planilha, mas
  funcionário não atualiza direito e ele não percebe até dar falta

### Persona 2 — Juliana, a atendente/operadora de estoque
- 24 anos, registra entrada de mercadoria e baixa de venda manual
  (quando o PDV não integra tudo)
- Usa o sistema em pé, no balcão, entre atender clientes — não tem
  paciência para telas lentas ou formulários longos
- Dor principal: registrar uma movimentação precisa ser rápido, senão
  ela pula essa etapa e o estoque desatualiza
- O que ela valoriza: poucos cliques, sem preencher campo que não
  muda todo dia (ex: não quer re-digitar nome do produto toda vez)

---

## 3. Goals and Non-Goals

### Goals (o que este produto se propõe a resolver)
- Dar ao dono uma visão **confiável** da quantidade real de cada
  produto, a qualquer momento
- Tornar o registro de movimentação rápido o suficiente para não virar
  fricção no fluxo de trabalho do funcionário
- Criar histórico auditável — toda mudança de estoque tem
  autor, data e motivo
- Ser utilizável por alguém sem treinamento técnico, com onboarding
  mínimo

### Non-Goals (explicitamente fora de escopo deste PRD)
- **Não é um PDV (ponto de venda)** — não processa pagamento, não
  emite nota fiscal. Pode integrar com um PDV no futuro, mas não
  substitui um.
- **Não é um ERP completo** — sem folha de pagamento, contabilidade,
  emissão fiscal.
- **Não inclui gestão de fornecedores com cotação/pedido de compra
  automatizado** no MVP — fica para V2/Later.
- **Não resolve, nesta versão, integração com marketplaces**
  (Mercado Livre, Shopee) — mencionado como possibilidade futura, não
  compromisso.

---

## 4. User Stories

**Dono/Gestor**
- Como dono, quero ver rapidamente quais produtos estão abaixo do
  estoque mínimo, para saber o que reabastecer sem contar
  manualmente.
- Como dono, quero ver o histórico de movimentações de um produto,
  para entender se uma divergência de contagem foi erro humano ou
  furto.
- Como dono, quero saber o valor total parado em estoque, para
  entender quanto capital está imobilizado.
- Como dono, quero controlar quem tem permissão para editar ou
  excluir produtos, para evitar erro ou fraude de funcionário.

**Funcionário/Operador**
- Como operador, quero registrar uma entrada ou saída de estoque em
  poucos cliques, para não atrasar meu atendimento no balcão.
- Como operador, quero ser impedido de registrar uma saída maior que
  o estoque disponível, para não gerar número negativo sem perceber.
- Como operador, quero buscar um produto pelo nome rapidamente, para
  não rolar uma lista longa.

**Ambos**
- Como usuário, quero fazer login com minha própria conta, para que
  minhas ações fiquem associadas a mim no histórico.

---

## 5. Feature List — MVP / V2 / Later

### MVP (deploy-ready, "pronto para uso real mesmo que incompleto")
Critério de corte usado: **o que é necessário para um dono confiar no
número de estoque e um funcionário conseguir operar sem fricção,
com segurança básica de acesso.** Isso é o padrão de mercado para um
MVP de B2B ferramenta operacional — funcional, seguro, sem
"enfeite".

- Cadastro, edição e exclusão de produto
- Registro de movimentação (entrada/saída) com validação de estoque
  insuficiente e concorrência segura
- Listagem com busca e paginação
- Histórico de movimentações por produto
- Autenticação (login obrigatório para ações de escrita)
- Alerta visual de estoque abaixo do mínimo
- Deploy público com HTTPS

### V2 (evolução direta, alta prioridade pós-MVP)
- Dashboard com métricas agregadas (valor total, produtos críticos,
  gráfico de movimentação)
- Permissões por papel (Operador vs. Gestor)
- API REST (para futura integração com PDV ou app mobile)
- Exportação de relatório (CSV/PDF)

### Later (visão de produto, sem compromisso de prazo)
- Multi-tenancy (múltiplas empresas na mesma instância) — **ver
  Questão Aberta #1**
- Gestão de fornecedores e pedido de compra
- Integração com PDV / marketplace
- Camada de IA sobre os dados de estoque (detalhada abaixo)
- App mobile nativo (hoje seria web responsivo)

#### Detalhamento da camada de IA (Later)

Deliberadamente fora do MVP: nenhuma das dores da Seção 1 (estoque
fantasma, falta de rastreabilidade, decisão de compra no escuro) exige
IA para ser resolvida — um dashboard com número confiável já resolve a
maior parte. IA aqui é um diferencial de produto sobre uma base já
sólida, não um requisito de confiabilidade. Por isso entra só depois
de MVP e V2 estarem consolidados (a API da Fase V2 é pré-requisito
técnico — a IA consome os mesmos endpoints/lógica de negócio).

- **Assistente conversacional no dashboard** — perguntas em linguagem
  natural ("quais produtos estão com estoque baixo?", "quanto saiu de
  X esse mês?") traduzidas em consultas ao sistema via tool calling.
  Resolve a persona Marcos, que "abre o sistema no fim do dia pra ver
  como estão as coisas" — reduz a fricção de interpretar tabela/gráfico.
- **Resumos automáticos em linguagem natural** — em vez de só números
  no dashboard, um texto gerado a partir dos dados agregados (ex: "o
  estoque de X caiu 30% essa semana, considere repor"). Baixo esforço
  de implementação uma vez que a API (V2) já expõe os dados agregados.
- **Sugestão de categoria automática** — ao cadastrar um produto só
  com o nome, sugerir a categoria com base em produtos semelhantes já
  cadastrados. Resolve parcialmente a dívida técnica assumida no MVP
  (categoria como texto livre, PRD 6.1) sem forçar um catálogo fechado
  de categorias.
- **Previsão de demanda / sugestão de reposição** — a partir do
  histórico de `Movimentacao`. **Nota de produto, não só técnica:**
  esta é a feature de IA com maior risco de gerar decisão financeira
  ruim se a previsão for ruim (o dono compra errado confiando na
  sugestão). Recomendo começar com um modelo estatístico simples
  (média móvel, `pandas`), não com IA generativa, e tratar como
  sugestão explicável ("baseado na média das últimas 4 semanas"), não
  como número automático de recompra.
- **Detecção de anomalias** — sinalizar movimentação fora do padrão
  (ex: saída muito maior que o normal para aquele produto), podendo
  indicar erro de digitação ou furto. Conecta diretamente ao Goal de
  rastreabilidade da Seção 3, mas é V-Later porque depende de volume
  histórico suficiente de movimentações para o padrão "normal" fazer
  sentido — não faz sentido tentar isso com poucos meses de dado real.

**Ordem de prioridade dentro do bloco de IA, se/quando for
implementado:** resumos automáticos e assistente conversacional
primeiro (baixo risco, alto valor percebido pelo Marcos); previsão de
demanda e detecção de anomalias por último (maior risco se errarem, e
dependem de mais dado histórico acumulado).

---

## 6. Detailed Functional Requirements — MVP

### 6.1 Cadastro de Produto
- Campos obrigatórios: nome, preço, quantidade mínima
- Campo opcional: categoria (texto livre no MVP — **flag:** texto
  livre gera inconsistência de dados ["Parafusos" vs "parafuso"];
  virar `select` com categorias pré-cadastradas é candidato a V2, não
  MVP, para não atrasar o cadastro)
- Preço deve ser > 0 (validação de servidor, não só client-side)
- Sistema não deve permitir dois produtos com nome idêntico na mesma
  categoria — **flag: regra de negócio não confirmada com stakeholder
  real; assumindo esse comportamento como razoável, mas precisa
  validação com um dono de comércio de verdade**

### 6.2 Movimentação de Estoque
- Tipo: Entrada ou Saída (obrigatório)
- Quantidade: inteiro positivo, obrigatório
- Motivo: texto livre, opcional no MVP (**flag:** para uso comercial
  real, "motivo" deveria provavelmente ser um campo estruturado —
  ex: Venda, Devolução, Perda, Ajuste de inventário — para permitir
  relatório por motivo depois. Deixar texto livre no MVP é aceitável
  para não atrasar entrega, mas é dívida técnica reconhecida)
- Sistema deve bloquear saída maior que a quantidade disponível,
  mostrando a quantidade real disponível no erro
- Toda movimentação registra o usuário autenticado que a realizou
- Operação deve ser atômica e segura contra concorrência (dois
  usuários registrando movimentação do mesmo produto simultaneamente
  não pode gerar estoque negativo)

### 6.3 Listagem e Busca
- Busca por nome (substring, case-insensitive)
- Paginação (10–20 itens por página)
- Cada linha exibe: nome, categoria, preço, quantidade atual,
  indicador visual se abaixo do mínimo
- Performance: listagem deve executar em número constante de queries
  ao banco, independente da quantidade de produtos (requisito técnico
  não-funcional, mas afeta diretamente a experiência em catálogos
  grandes)

### 6.4 Autenticação
- Login obrigatório para: cadastrar, editar, excluir produto,
  registrar movimentação
- Visualização de listagem pode ser pública ou não —
  **flag: decisão de produto não tomada.** Para um comércio real,
  provavelmente tudo deveria exigir login (não há razão de negócio
  para estoque ser público). Recomendo login obrigatório para tudo no
  MVP, mas sinalizando que isso é uma escolha, não um dado.
- Senha nunca armazenada em texto puro (hashing padrão)

### 6.5 Alerta de Estoque Baixo
- Produto é sinalizado quando quantidade atual < quantidade mínima
  definida no cadastro
- Sinalização visível na listagem, sem necessidade de entrar no
  detalhe do produto

### 6.6 Deploy
- Ambiente de produção com HTTPS obrigatório
- Variáveis sensíveis (senha de banco, chave secreta) fora do
  código-fonte
- Banco de dados relacional apropriado para múltiplos acessos
  simultâneos (não SQLite em produção)

---

## 7. Data Model Sketch

```
Usuario (auth nativo do framework)
├── id
├── username
├── password (hash)
└── grupo (papel — Operador/Gestor, V2)

Produto
├── id
├── nome
├── categoria (texto livre — MVP; FK para Categoria — V2, ver flag 6.1)
├── preco
├── quantidade_minima
├── criado_em
└── empresa_id (FK → Empresa — decidido, ver Questão Aberta #1 resolvida)

Movimentacao
├── id
├── produto_id (FK → Produto)
├── tipo (Entrada | Saída)
├── quantidade
├── data
├── motivo (texto livre — MVP; enum estruturado — V2, ver 6.2)
└── usuario_id (FK → Usuario, nullable)

[V2] Categoria
├── id
├── nome
└── empresa_id (FK → Empresa — decidido, ver Questão Aberta #1 resolvida)

Empresa (multi-tenancy decidido — ver Questão Aberta #1 resolvida)
├── id
├── nome
└── plano/assinatura

Membership (vínculo usuário ↔ empresa, ver Questão Aberta #1 resolvida)
├── id
├── usuario_id (FK → Usuario, OneToOne)
└── empresa_id (FK → Empresa)
```

**Nota de design:** a quantidade atual do produto **não é um campo
armazenado diretamente** — é derivada da soma de `Movimentacao`. Essa
é uma decisão deliberada de auditabilidade (você sempre consegue
reconstruir "como chegamos nesse número"), com o trade-off de custo
computacional em catálogos muito grandes, mitigável com agregação
otimizada ou, no limite, desnormalização futura.

---

## 8. Edge Cases and Failure States

| Cenário | Comportamento esperado |
|---|---|
| Dois usuários registram saída do mesmo produto ao mesmo tempo, cada um dentro do limite individual, mas juntos excedem o estoque | Sistema deve processar uma por vez (lock), a segunda deve ver o estoque já atualizado e ser bloqueada se necessário |
| Usuário tenta registrar saída maior que o disponível | Erro claro, mostrando quantidade disponível real, nenhum registro é criado |
| Produto excluído tem histórico de movimentações | **Decidido (2026-08-19):** soft delete. Excluir um produto não apaga fisicamente o registro nem seu histórico de `StockMovement` — apenas marca `active=False`. Queryset padrão (`Product.objects.active()`) exclui produtos inativos da listagem, preservando auditabilidade. Implementado em `319e767`/`6bd8058`. |
| Usuário perde conexão no meio do registro de uma movimentação | Nenhuma escrita parcial no banco — operação deve ser atômica (já coberto pela transação) |
| Preço ou quantidade inserido como texto/negativo | Validação de servidor rejeita, nunca só validação de front-end |
| Sessão expira enquanto usuário preenche formulário longo | Sistema deve redirecionar para login sem perder claramente o que causou o erro (mensagem clara, não erro técnico cru) |
| Busca de produto sem resultado | Mensagem clara de "nenhum produto encontrado", não tela em branco |
| Categoria com nome digitado de formas diferentes ("Ferramentas" / "ferramentas") | No MVP isso é uma limitação conhecida e aceita (texto livre); vira bug de dado sujo até virar campo estruturado em V2 |

---

## 9. Success Metrics

Métricas de produto, assumindo uso real por um comércio (não métricas
de portfólio/acadêmicas):

**Adoção**
- % de movimentações de estoque registradas no sistema vs. estimativa
  de movimentações reais (proxy: comparar contagem física periódica
  com o número do sistema — divergência baixa = alta adoção real)
- Nº de logins ativos por semana por comércio

**Confiabilidade (a dor #1 do problem statement)**
- Divergência entre contagem física e sistema, medida em auditorias
  periódicas (meta: reduzir divergência ao longo do tempo, não zerar
  imediatamente)

**Eficiência de uso**
- Tempo médio para registrar uma movimentação (proxy de fricção —
  a persona Juliana abandona se isso for lento)
- Taxa de erro/retrabalho ao preencher formulário (quantas vezes um
  formulário é submetido com erro de validação)

**Técnica (suporte aos objetivos acima)**
- Uptime do sistema em produção
- Tempo de resposta da listagem de produtos sob volume crescente

**Métrica que eu **não** usaria como sucesso principal:** número total
de produtos cadastrados — é uma métrica de vaidade, não indica se o
sistema está resolvendo a dor real (confiabilidade do número).

---

## 10. Open Questions

1. ~~**Multi-tenancy: decidir agora ou depois?**~~ — **Resolvido
   (2026-08-21): multi-tenant desde já.** Justificativa: existe
   intenção real de negócio por trás da pergunta, não curiosidade
   técnica — o plano é liberar o sistema para duas empresas em teste.
   Adiar teria significado migrar dados reais de single-tenant para
   multi-tenant depois, mais caro e arriscado do que nascer
   multi-tenant.

   Decisão de arquitetura (ver Seção 7 para o schema):
   - Model `Empresa` novo; `Produto.empresa_id` (FK obrigatória,
     `on_delete=PROTECT`) é o único ponto do schema que carrega
     empresa — `Movimentacao` não duplica a FK, alcança a empresa via
     `movimentacao.produto.empresa` (mesma filosofia de fonte única já
     usada pela quantidade atual do produto, ver nota de design
     abaixo).
   - Vínculo usuário↔empresa via model `Membership`
     (`OneToOneField(Usuario)` + `FK(Empresa)`), sem trocar o model de
     usuário nativo do Django (`AUTH_USER_MODEL`) — trocar o model de
     usuário é caro de desfazer e não resolve um problema que
     temos (não precisamos mudar o que é um usuário, só anexar a
     empresa a ele).
   - Isolamento de dado é obrigatório em todo lookup de objeto
     específico (detalhe, edição, exclusão, registro de movimentação),
     não só em listagens — ver dono da empresa A não pode acessar
     produto da empresa B nem digitando a URL direto.
   - Papel (Gestor/Operador) via `django.contrib.auth.models.Group`,
     mecanismo que a Seção 7 já previa para V2 — adiantado agora para
     restringir quem pode desativar/reativar produto a usuários do
     grupo Gestor.
   - Django admin deixa de ser ferramenta de uso do dono/gerente e
     vira interna/dev-only (só superusuário) — evita vazamento de
     dado entre empresas por esse caminho sem precisar duplicar lógica
     de isolamento dentro do admin.
   - Sequenciamento: implementado depois dos itens de robustez do
     audit de 2026-08-20 que tocam o mesmo código
     (`movement_create`, `services.register_movement()`), para servir
     de rede de segurança contra regressão antes da mudança.

2. ~~**Soft delete vs. exclusão física de produto**~~ — **Resolvido
   (2026-08-19): soft delete**, via campo `Product.active` (ver Seção 8).

3. **Listagem de produtos deve ser pública ou exigir login sempre?**
   Recomendação dada em 6.4, mas não confirmada como decisão de
   produto.

4. **Categoria como texto livre ou catálogo estruturado desde o
   MVP?** Afeta qualidade de relatório futuro; texto livre é mais
   rápido de entregar, mas gera dívida de dados sujos.

5. **Quem é o comprador real deste produto?** O PRD assume "comércio
   local genérico", mas não sabemos se o plano é vender para 1 loja
   específica (piloto), ou desenhar já pensando em múltiplos
   clientes pagantes — isso muda diretamente a prioridade entre
   "polir a experiência de 1 usuário" vs. "construir para escalar
   comercialmente" desde já.

6. **Existe orçamento para infraestrutura paga (banco gerenciado,
   hosting)?** O roadmap técnico assume free-tier no MVP; isso é
   adequado para validar o produto, mas free-tier tem limites de
   uptime/performance que podem contradizer a métrica de
   confiabilidade da Seção 9 se o uso real crescer.