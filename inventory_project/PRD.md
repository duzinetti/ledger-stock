# PRD — Sistema de Gerenciamento de Estoque para Pequeno Comércio

**Autor:** Eduardo Zinetti (Dudu) | **Documento preparado como exercício de Product Management**
**Status:** Draft v1
**Última atualização:** 2026-08-17

---

## 0. Premissas assumidas (flagged, não inventadas silenciosamente)

Antes do PRD em si, deixo explícito o que assumi para poder avançar, já
que você delegou algumas decisões:

- **MVP definido por mim (pergunta 2):** delimitei o MVP como CRUD de
  produtos + movimentação de estoque com concorrência segura +
  autenticação básica + deploy. Justificativa no item 5.
- **Multi-tenancy (pergunta 3) é a decisão arquitetural mais crítica
  deste documento** — ver Seção 9, Questão Aberta #1. Você respondeu
  "eventualmente", o que **não é uma resposta neutra**: decidir agora
  vs. depois muda o data model desde o dia 1. Estou tratando isso como
  requisito não resolvido, não decidindo por você.
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
- Previsão de demanda / sugestão de reposição (com ou sem IA)
- App mobile nativo (hoje seria web responsivo)

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
└── [FUTURO, se multi-tenant] empresa_id (FK)

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
└── [FUTURO, se multi-tenant] empresa_id (FK)

[LATER] Empresa (só existe se multi-tenant for adotado)
├── id
├── nome
└── plano/assinatura
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
| Produto excluído tem histórico de movimentações | **Flag: decisão não tomada.** Excluir o produto apaga o histórico junto (cascade) ou deveria "arquivar" em vez de excluir, preservando auditoria? Para um sistema comercial real, recomendo **soft delete** (campo `ativo=False`) em vez de exclusão física, para não perder rastreabilidade — isso muda o MVP se aceito. |
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

1. **Multi-tenancy: decidir agora ou depois?** Esta é a questão mais
   cara do documento. Se a resposta de longo prazo é "sim,
   eventualmente", a arquitetura de dados do MVP deveria **já**
   incluir a FK de `empresa` em `Produto`/`Movimentacao` desde o
   início — migrar um sistema single-tenant para multi-tenant depois
   que já tem dados reais é significativamente mais caro e arriscado
   do que nascer multi-tenant com uma única empresa cadastrada.
   **Recomendação:** decidir isso antes de iniciar a Fase 2 (banco de
   dados) do roadmap técnico, não depois.

2. **Soft delete vs. exclusão física de produto** — impacta
   diretamente auditabilidade, que é um dos goals centrais do
   produto (ver Seção 8).

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
