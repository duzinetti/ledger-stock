# Gerenciador de Estoque - Documento de Requisitos

## 1. Objetivo

Sistema web para controle de estoque de produtos, permitindo cadastro de
produtos, registro de movimentações (entrada e saída) e visualização da
quantidade atual em estoque, com alerta para produtos abaixo do mínimo
definido.

## 2. Escopo

Aplicação web construída em Django, com banco de dados relacional
(SQLite no desenvolvimento, podendo migrar para MySQL/PostgreSQL).

## 3. Requisitos Funcionais

| ID    | Descrição                                                              |
|-------|--------------------------------------------------------------------------|
| RF01  | O sistema deve permitir cadastrar um produto (nome, categoria, preço, quantidade mínima) |
| RF02  | O sistema deve permitir editar e remover um produto                     |
| RF03  | O sistema deve permitir listar todos os produtos cadastrados            |
| RF04  | O sistema deve permitir registrar uma movimentação de entrada de estoque |
| RF05  | O sistema deve permitir registrar uma movimentação de saída de estoque   |
| RF06  | O sistema deve calcular a quantidade atual de um produto a partir do histórico de movimentações |
| RF07  | O sistema deve listar o histórico de movimentações de um produto        |
| RF08  | O sistema deve sinalizar produtos com quantidade atual abaixo da quantidade mínima |
| RF09  | O sistema deve permitir busca de produtos por nome ou categoria         |
| RF10  | O sistema deve impedir registro de saída maior que a quantidade disponível |

## 4. Requisitos Não Funcionais

| ID    | Descrição                                                        |
|-------|---------------------------------------------------------------------|
| RNF01 | O sistema deve ser desenvolvido em Django (Python)                  |
| RNF02 | O banco de dados deve ser relacional (SQLite em dev)                 |
| RNF03 | A interface administrativa (Django Admin) deve estar disponível para gestão rápida de dados |
| RNF04 | O código deve seguir a separação de camadas padrão do Django (models, views, templates) |

## 5. Modelo de Dados

### Produto
- id (PK)
- nome
- categoria
- preco
- quantidade_minima
- criado_em

### Movimentacao
- id (PK)
- produto (FK -> Produto)
- tipo (E = entrada, S = saída)
- quantidade
- data
- motivo

A quantidade atual de um produto **não é armazenada diretamente** — é
calculada somando entradas e subtraindo saídas do histórico de
movimentações. Isso garante rastreabilidade completa do estoque.

## 6. Fora de escopo (por ora)

- Autenticação/permissões por usuário
- API REST (Django REST Framework)
- Gestão de fornecedores
- Relatórios/exportação de dados

## 7. Roadmap de desenvolvimento

1. Models + Django Admin (validar estrutura de dados)
2. Views e templates básicos (listar, cadastrar, editar produto)
3. Views de movimentação (entrada/saída)
4. Cálculo de quantidade atual e alerta de estoque baixo
5. Busca de produtos
6. Estilização (por último)
