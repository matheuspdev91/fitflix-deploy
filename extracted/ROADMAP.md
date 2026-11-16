# Foundation CSS — Roadmap de Refatoração

> Objetivo: transformar a Foundation em um Design System modular, escalável e reutilizável, preservando compatibilidade com o Fitflix durante toda a migração.

---

# Status Geral

- [x] Auditoria arquitetural
- [x] Definição da estrutura da Foundation
- [ ] Consolidação dos Design Tokens
- [ ] Estrutura Base
- [ ] Layout Primitives
- [ ] Componentização
- [ ] Migração dos Templates
- [ ] Expurgo do CSS legado

---

# Fase 1 — Design Tokens

## Objetivo

Centralizar todos os tokens do sistema.

### Estrutura

- [ ] tokens.css
- [ ] colors.css
- [ ] spacing.css
- [ ] typography.css
- [ ] radius.css
- [ ] shadows.css
- [ ] transitions.css
- [ ] layout.css
- [ ] z-index.css

### Refatoração

- [ ] Remover variables.css
- [ ] Migrar todas as variáveis
- [ ] Eliminar duplicações
- [ ] Padronizar nomenclatura

---

# Fase 2 — Base

## Objetivo

Criar a camada responsável pelos estilos globais.

### Arquivos

- [x] reset.css
- [ ] base.css

### Refatoração

- [ ] Mover estilos globais do body
- [ ] Mover estilos do html
- [ ] Padronizar tipografia base
- [ ] Padronizar links
- [ ] Padronizar listas

---

# Fase 3 — Layout

## Objetivo

Criar primitivas reutilizáveis de layout.

### Estrutura

- [ ] container.css
- [ ] section.css
- [ ] stack.css
- [ ] cluster.css
- [ ] grid.css
- [ ] sidebar.css
- [ ] navbar.css

### Refatoração

- [ ] Remover layouts duplicados
- [ ] Remover containers específicos
- [ ] Padronizar grids
- [ ] Padronizar responsividade

---

# Fase 4 — Utilities

## Objetivo

Manter apenas utilitários genéricos.

### Arquivos

- [x] utilities.css
- [x] animations.css

### Auditoria

- [ ] Remover utilities mortas
- [ ] Padronizar nomenclatura
- [ ] Eliminar duplicações

---

# Fase 5 — Componentes

## Objetivo

Construir um Design System completo.

## Componentes

### Botões

- [ ] Button

### Formulários

- [ ] Input
- [ ] Select
- [ ] Textarea
- [ ] Checkbox
- [ ] Radio
- [ ] Switch

### Estrutura

- [ ] Card
- [ ] Modal
- [ ] Drawer
- [ ] Accordion
- [ ] Tabs

### Feedback

- [ ] Alert
- [ ] Badge
- [ ] Toast
- [ ] Spinner

### Navegação

- [ ] Navbar
- [ ] Sidebar
- [ ] Breadcrumb
- [ ] Pagination

### Dados

- [ ] Table
- [ ] Avatar
- [ ] Tooltip
- [ ] Dropdown

---

# Fase 6 — Templates

## Objetivo

Migrar o Fitflix para utilizar exclusivamente a Foundation.

### Refatoração

- [ ] Remover classes antigas
- [ ] Padronizar HTML
- [ ] Substituir estilos locais
- [ ] Utilizar apenas componentes da Foundation

---

# Fase 7 — Limpeza

## Objetivo

Eliminar código legado.

### Remoções

- [ ] style.css
- [ ] fitflix.css
- [ ] CSS duplicado
- [ ] Classes mortas
- [ ] Variáveis não utilizadas

---

# Fase 8 — Documentação

## Objetivo

Transformar a Foundation em uma biblioteca reutilizável.

### Documentação

- [ ] Estrutura de pastas
- [ ] Convenções
- [ ] Guia de componentes
- [ ] Guia de tokens
- [ ] Guia de layout
- [ ] Guia de utilities
- [ ] Exemplos de uso

---

# Critério de Conclusão

A Foundation será considerada concluída quando:

- Não existir CSS duplicado.
- Todos os componentes utilizarem Design Tokens.
- O Fitflix utilizar exclusivamente componentes da Foundation.
- Não existir CSS específico fora da camada de páginas.
- A Foundation puder ser reutilizada em outro projeto sem alterações.