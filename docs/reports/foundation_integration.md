# Plano Oficial de Integração: Foundation & Fitflix

=========================================================
## 1. OBJETIVO
=========================================================
O objetivo deste documento é estabelecer a estratégia oficial de engenharia para integrar a biblioteca **Foundation** ao monolito **Fitflix**.
- **Papel da Foundation:** Atuar como um pacote de infraestrutura genérico e agnóstico de domínio (Shared Library). Ela proverá pipelines de mídia, sincronização com Cloudinary, parsers, normalizadores e configurações globais.
- **Papel do Fitflix:** Atuar estritamente como a camada de Aplicação e Domínio de Negócios (Saúde/SaaS). O Fitflix cuidará de treinos, antropometria, autenticação web e renderização de views (Django).
- **Coexistência:** A Foundation será injetada no Fitflix como uma dependência arquitetural (podendo ser consumida via `pip install` de um repositório interno ou submódulo). O Fitflix importará a Foundation para delegar todo o trabalho sujo de infraestrutura (como varredura de arquivos e uploads em nuvem), limpando seu próprio repositório.

=========================================================
## 2. VISÃO GERAL DA ARQUITETURA
=========================================================
Após a integração, a arquitetura obedecerá ao princípio de Inversão de Dependência (Clean Architecture):

```text
[ FOUNDATION ]
      ↓
[ BIBLIOTECA COMPARTILHADA (Infra/Pipeline/Clients) ]
      ↓ (Importada pelo Fitflix via dependência)
[ FITFLIX ]
      ↓
[ APLICAÇÃO DE DOMÍNIO (Views/Models/Templates) ]
```
O fluxo será unidirecional. A Foundation jamais conhecerá a existência do Fitflix. O Fitflix, por sua vez, acoplará suas rotinas de background aos contratos limpos fornecidos pela Foundation.

=========================================================
## 3. INVENTÁRIO DA FOUNDATION
=========================================================
A Foundation possui módulos consolidados orientados a infraestrutura:
- **`cloudinary_sync/`**: Sincronização e upload remoto. (Maturidade: Alta | Reutilização: Universal)
- **`pipeline/` / `media/`**: Orquestração de fluxos de processamento. (Maturidade: Alta | Reutilização: Alta)
- **`parser/` / `matcher/`**: Heurísticas de detecção de strings e arquivos. (Maturidade: Média | Reutilização: Alta)
- **`exceptions/`**: Central de tratamento de erros. (Maturidade: Alta | Reutilização: Universal)
- **`config.py` / `clients/`**: Gestores de chaves de API e conexões. (Maturidade: Alta | Reutilização: Alta)
- **`exports/` / `enricher/`**: Exportação de dados (JSON) e enriquecimento. (Maturidade: Média)

=========================================================
## 4. INVENTÁRIO DO FITFLIX
=========================================================
Principais módulos do ecossistema Django:
- **`core.models`**: Agrupa pacientes, treinos e catálogo. (Responsabilidade: Domínio puro. Acoplamento: Alto ao Django ORM).
- **`core.views` & `core.forms`**: Lógica de roteamento web e validação. (Responsabilidade: Interface web. Acoplamento: Alto ao frontend).
- **`core/media_pipeline/`**: O clone legado da Foundation. Possui `scanner.py`, `matcher.py`, `auditor.py`. (Responsabilidade: Processamento de GIFs offline. Acoplamento: Totalmente redundante).
- **`core/management/commands/`**: Scripts de sincronização isolados (ex: `upload_gifs_cloudinary.py`). (Acoplamento: Alto com a API externa).

=========================================================
## 5. MATRIZ DE COMPATIBILIDADE
=========================================================

| Foundation | Fitflix | Compatível | Deve integrar | Prioridade | Justificativa |
| --- | --- | --- | --- | --- | --- |
| `cloudinary_sync` | `upload_gifs_cloudinary.py` | Sim | Sim | Alta | A Foundation já encapsula as chamadas de API, o script do Fitflix deve apenas instanciar o sync. |
| `matcher` / `parser` | `core/media_pipeline/` | Sim | Sim | Alta | O submódulo interno do Fitflix é uma cópia da infraestrutura que pertence à Foundation. Deve ser substituído. |
| `config.py` | `projeto/settings.py` | Sim | Sim | Média | A leitura de `.env` de segurança do Cloudinary e logs deve ser puxada pela config da Foundation. |
| `domain` | `core.models` | Não | Não | - | Modelos do Fitflix (Alunos, Treinos) pertencem unicamente ao SaaS de saúde e não à Foundation. |
| `exceptions` | Try/Excepts nas Views | Sim | Sim | Baixa | Padronizar as capturas de falha de I/O em formulários. |

=========================================================
## 6. O QUE DEVE PERMANECER NO FITFLIX
=========================================================
O Fitflix conservará todo o seu coração de regras de negócios.
- **Domínio Antropométrico:** `AvaliacaoFisica`, `Adipometria`, `Circunferencia`. (Medidas médicas não são infraestrutura).
- **Domínio Esportivo:** `Treino`, `ExercicioTreino`. 
- **IAM (Identity):** `Usuario`, Sessões, Cookies e Views (Dashboards).
*Motivo:* Mover lógica de negócio para a Foundation a transformaria num "Frankenstein" acoplado ao Fitflix. A Foundation deve servir para qualquer projeto, logo, regras de personal trainer pertencem unicamente ao Fitflix.

=========================================================
## 7. O QUE DEVE SER CENTRALIZADO NA FOUNDATION
=========================================================
Toda a mecânica que lida com abstração de arquivos, APIs ou utilitários puros.
- **Cloudinary Sync:** Uploads, exclusões e formatação de URLs seguras.
- **Pipeline de Media:** Todo o código de `core/media_pipeline/` do Fitflix (que engloba ler pastas, validar Regex de MP4/GIF e achar arquivos soltos).
- **Config & Secrets Manager:** Para garantir que falhas de `DEBUG = True` ou leitura de `.env` quebrem a aplicação logo na raiz.
- **Logging genérico e Handlers de Erro:** Para parar de usar `print()` solto em *Management Commands*.

=========================================================
## 8. DEPENDÊNCIAS
=========================================================
- **Grafo Desejado:** `Fitflix` → Importa → `Foundation`.
- **Acoplamento atual a ser quebrado:** Hoje o Fitflix (`core/media_pipeline`) importa bibliotecas sistêmicas cruas (`os`, `re`, `cloudinary`) repetindo rotinas que a Foundation já resolveu.
- **Ciclos:** O perigo é o desenvolvedor tentar importar Models do Fitflix (`VariacaoExercicio`) dentro da Foundation. Isso geraria dependência circular fatal. Para resolver, o Fitflix passará DTOs (Dicionários simples ou instâncias agnósticas) para a Foundation agir.

=========================================================
## 9. ESTRATÉGIA DE MIGRAÇÃO
=========================================================
A integração será puramente **Incremental** e executada em modelo *Strangler Fig Pattern*.
- Jamais reescrever as Views do Django na primeira semana.
- Começar pelos "frutos mais baixos": scripts de linha de comando (`management/commands`) que processam mídia.
- Desligar o módulo legado do Fitflix apenas quando a importação equivalente da Foundation já estiver passando nos testes locais de exportação JSON/Upload.

=========================================================
## 10. ORDEM DE INTEGRAÇÃO
=========================================================
- **Sprint 1: Empacotamento e Config**
  - Instalar a Foundation via `pyproject.toml` no ambiente do Fitflix (ex: dependência local `pip install -e ../foundation`).
  - Trocar o carregador de `.env` do Fitflix pelo validador seguro da `config.py` da Foundation.
- **Sprint 2: Extirpação do Media Pipeline Legado**
  - Refatorar o script `scan_midias.py` e `sugerir_gifs.py` para utilizar o `scanner` e `matcher` nativos da Foundation.
  - Deletar a pasta duplicada `core/media_pipeline` inteira.
- **Sprint 3: Conexão Cloudinary Segura**
  - Substituir a implementação manual de `upload_gifs_cloudinary.py` pelo cliente orquestrador `cloudinary_sync` da Foundation.
- **Sprint 4: Exportadores (Opcional/Avançado)**
  - Utilizar o `JsonExporter` da Foundation para gerar os dumps estáticos do banco do Fitflix ao invés do script rudimentar existente.

=========================================================
## 11. RISCOS
=========================================================

| Risco | Impacto | Probabilidade | Mitigação |
| --- | --- | --- | --- |
| Dependência Circular | Crítico | Alta | Impor regra estrita de Code Review: A Foundation nunca importa nada da pasta `core/`. |
| Quebra de compatibilidade no Matcher de GIFs | Alto | Média | Validar o `inventory` no ambiente legado comparado ao gerado pela Foundation (Testes de Regressão em CSV). |
| Crash em Produção por caminhos absolutos locais | Crítico | Baixa | A Foundation utiliza caminhos relativos de `Pathlib`, basta mockar no teste no CI antes do Deploy. |

=========================================================
## 12. PLANO DE TESTES
=========================================================
- **Sprint 1 (Config):** Validação: Subir o `runserver` do Fitflix e confirmar se o `DEBUG` obedece à injeção da Foundation sem quebrar o PostgreSQL. 
- **Sprint 2 (Pipeline):** Comparar os dumps gerados pelo comando *antigo* com o novo. *Critério de Sucesso:* 0 diferenças textuais nos arquivos CSV mapeados de GIFs órfãos. Rollback via `git restore core/media_pipeline`.
- **Sprint 3 (Upload):** Criar pastas MOCK temporárias e disparar a Foundation. Checar no Dashboard do Cloudinary se 5 mídias subiram corretamente sem afetar o banco principal.

=========================================================
## 13. GANHOS ESPERADOS
=========================================================
- **Redução de Duplicação:** Exclusão de toda a pasta `core/media_pipeline/` (+ de 15 arquivos), removendo milhares de linhas mortas do Fitflix.
- **Desacoplamento:** O SaaS de Saúde focará 100% em renderizar dashboards de emagrecimento, enquanto a Foundation focará silenciosamente em subir imagens sem bugar os formulários.
- **Padronização:** Uniformidade nos relatórios via CSV e exportadores, mitigando gambiarras nos *Management Commands*.
- **Escalabilidade:** Ao extrair a infraestrutura pesada, novos serviços SaaS podem brotar (como NutriAI) importando a mesmíssima Foundation testada.

=========================================================
## 14. ROADMAP DA INTEGRAÇÃO
=========================================================
- **Fase A (Fundação):** Instalação via pacote, mapeamento de caminhos, importação inicial, substituição do `dotenv`.
- **Fase B (Varredura e Match):** Migração das lógicas cruas de reconhecimento de padrões (Regex de Gifs e varreduras locais).
- **Fase C (Nuvem e Uploads):** Delegação da camada I/O (Envio Cloudinary).
- **Fase D (Limpeza):** Purga do código legado e dead-code do Fitflix.

=========================================================
## 15. RECOMENDAÇÕES
=========================================================
- **Configuração no `pyproject.toml`:** Transforme o projeto Foundation em um pacote Python de verdade, instalável. Não faça cópia manual de arquivos (Copiar e colar código).
- **Adaptação dos Models do Django:** Quando chamar a Foundation num `management command`, passe listas primitivas do Python (strings, UUIDs) ao invés de passar QuerySets do ORM, isolando a memória.
- **Não refatore Front-end agora:** O plano de integração afeta puramente o Backend/Infra. Ignore as injeções CSS nas views durante essa fase para reduzir o "Blast Radius".

=========================================================
## 16. CONCLUSÃO
=========================================================
A integração entre Fitflix e Foundation é o pilar que conduzirá o projeto de um MVP amador (Monolito inchado) a um SaaS Profissional. O plano fundamenta-se num eixo inviolável: a infraestrutura deve servir à Aplicação, e nunca o inverso. Através de uma integração estritamente incremental focada inicialmente nos bastidores (Background Tasks e Uploads), extirpa-se de forma gradual as monstruosidades contidas em `core/media_pipeline/` preservando intacta a estabilidade das Views e da Autenticação do sistema. Uma migração maciça corromperia o domínio. Ao seguir este guia modular faseado (Sprints 1 a 4), colhemos ganhos imediatos de legibilidade, evitamos dependências circulares e consagramos a Arquitetura Limpa, blindando o ecossistema para escala de negócios futuros.
