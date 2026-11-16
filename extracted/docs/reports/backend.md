# Auditoria do Backend - Fitflix

====================================================
## 1. RESUMO EXECUTIVO
====================================================

O backend do projeto Fitflix encontra-se em um **nível de maturidade inicial/MVP** (Minimum Viable Product). 
A **organização geral** é monolítica e excessivamente centralizada em um único aplicativo Django chamado `core`. A **qualidade da implementação** é mista: apresenta bom uso de recursos do ORM e transações, porém sofre gravemente com problemas arquiteturais de design de software (como *Fat Views* e vazamento de regras de negócio para a camada de apresentação).
A **aderência ao Django** é forte no que diz respeito ao padrão MTV (Model-Template-View) e configurações, no entanto falha em seguir a filosofia de componentes reutilizáveis (*pluggable apps*). A **impressão geral** é de um projeto que cumpriu seu propósito de lançamento rápido, mas que atualmente acumula dívida técnica e demanda refatoração urgente para suportar crescimento saudável.

====================================================
## 2. ESTRUTURA DO BACKEND
====================================================

- **Apps Django:** Centralizados em apenas um app funcional (`core`), tornando o sistema engessado.
- **Organização dos módulos:** Maioria do código concentrada na raiz do `core` (`models.py`, `views.py`, `forms.py`).
- **Services:** Incipientes (`core/email_service.py` e `core/services/fitflix_persister.py`). 
- **Utils:** Incipientes (`core/util/gif.py` e `core/util/texto.py`).
- **Management commands:** Existentes e focados na gestão de catálogo (ex: `upload_gifs_cloudinary.py`, `vincular_gifs.py`).
- **Sinais (Signals):** Não foram encontrados sinais declarados isoladamente, indicando acoplamento síncrono.
- **Forms:** Bem utilizados e centralizados em `forms.py`.
- **Admin:** Completo e detalhado (`core/admin.py`), cobrindo praticamente todos os modelos com inlines e actions customizadas.
- **Middleware:** Apenas middlewares padrão do framework e Whitenoise configurados em `settings.py`.
- **Urls:** Centralizadas em `core/urls.py` e mal categorizadas.
- **Settings:** Bem estruturado (`projeto/settings.py`), adotando "12-Factor" com variáveis de ambiente (Cloudinary, Postgres, Secret Key).

**Avaliação: Regular**
*Justificativa:* Apesar de possuir infraestrutura robusta de settings e boa configuração do Admin, a ausência de divisões em apps de contexto (ex: `users`, `workouts`, `catalog`) gera um acoplamento sistêmico perigoso na raiz do projeto.

====================================================
## 3. MODELS
====================================================

- **Organização e Responsabilidades:** O arquivo `core/models.py` abriga tudo: de Autenticação (`Usuario`), Domínio de Alunos e Avaliações (`Aluno`, `AvaliacaoFisica`), até o Domínio de Catálogo de Exercícios (`VideoExercicio`, `VariacaoExercicio`).
- **Relacionamento e ORM:** O uso das relações como `ForeignKey` e `OneToOneField` está correto na sintaxe. Há boa prática no uso de `related_name` para reverse queries (ex: `related_name="alunos"`, `related_name="circunferencias"`).
- **Constraints / Indexes:** Não foram identificados `indexes` customizados ou `UniqueConstraint` complexos, o que pode impactar a performance se o banco crescer.
- **Meta / Verbose Name:** Falha na adoção sistemática de classes `Meta` com `verbose_name`, `verbose_name_plural` e `ordering` nos modelos.

**Avaliação:**
- **Coesão:** Baixa (Mistura agregados não relacionados no mesmo arquivo).
- **Acoplamento:** Alto (Modelos de Treino amarrados a Modelos de Vídeos estáticos).
- **Reutilização:** Baixa.
- **Modelos Grandes:** Não há uma única tabela absurdamente grande (como 50 campos soltos), graças à separação pontual através de herança via `OneToOneField` em `Circunferencia` e `Adipometria`.

====================================================
## 4. VIEWS
====================================================

- **Tamanho das views:** Extremo. O arquivo `core/views.py` possui mais de 800 linhas.
- **Responsabilidades:** Agrupam controle de roteamento, processamento de formulários, persistência de banco de dados e algoritmos de cálculo.

**Identificação de Problemas (Exemplos):**
- **Fat Views / Regras de negócio HTTP:** A função `dashboard(request, id)` calcula a composição corporal (`calcular_composicao`) e itera em dicionários comparativos dentro da view, o que é pura regra de negócios.
- **Código Duplicado / Semântica Mista:** Funções como `gerar_senha_aleatoria()` e `criar_aluno_minimo()` estão declaradas soltas dentro do arquivo `views.py` de roteamento, quebrando totalmente a semântica.
- **Oportunidades para Services:** A criação conjunta de avaliações em `criar_avaliacao_idoso` (onde Avaliação + Circunferência + Adipometria são salvos juntos) deveria viver em uma transação dentro de um `AssessmentService.create_elder_assessment(...)`.

====================================================
## 5. FORMS
====================================================

- **ModelForms:** Amplamente utilizados de forma correta e nativa para quase todas as entidades.
- **Validações:** Uso regular da função `clean()`. No `TreinoForm`, o método `clean()` valida se o usuário selecionou um aluno existente ou digitou um nome novo, garantindo integridade. 
- **Reaproveitamento:** Há o reaproveitamento de widgets em múltiplos forms, porém a injeção de classes CSS dentro do método `__init__` do Form mistura a lógica de apresentação no Backend de forma imperativa (ex: `field.widget.attrs["class"] = f"{existing_class} {field_classes}".strip()`).

====================================================
## 6. SERVICES
====================================================

- **Existência:** Existem pequenos serviços isolados, como `core/email_service.py` e `core/services/fitflix_persister.py`. O módulo `media_pipeline` possui uma vasta gama de classes em formato Service.
- **Responsabilidades:** Restritas. O grosso do sistema ignora os services.
- **Isolamento:** As Views (camada de apresentação) ainda retêm pesadas lógicas de negócio transacionais, regras de persistência complexa (criação de exercícios em lote) e algoritmos matemáticos (IMC/Percentual Gordura).

====================================================
## 7. UTILS
====================================================

- **Existência e Localização:** Existem as pastas `core/util/` contendo `gif.py` e `texto.py`. 
- **Inadequação:** Utilitários vitais para as Views, como `gerar_senha_aleatoria()` e `calcular_composicao()`, vivem soltos dentro de `core/views.py`, indicando desorganização estrutural.

====================================================
## 8. MANAGEMENT COMMANDS
====================================================

- **Organização:** Presentes em `core/management/commands/`. 
- **Responsabilidades:** Muito focados no upload de vídeos e gerenciamento em lote (`vincular_gifs.py`, `upload_gifs_cloudinary.py`). 
- **Boas Práticas:** Seguem a estrutura correta de scripts do Django (`BaseCommand`), utilizando ORM de forma explícita e controlada para manutenção remota.

====================================================
## 9. ORM
====================================================

- **Uso Positivo:** Identificado o uso correto de `select_related("exercicio", "variacao")` e `prefetch_related("variacoes")` em diversas views (como `treino_detail` e `fitflix`) e commands, o que evita o problema crítico das consultas "N+1". O operador `Q` é usado de forma elegante na view `treino_detail` para filtrar permissões de dono ou criador: `Q(id=treino_id, aluno__personal=request.user) | Q(...)`.
- **Ineficiências:** Não há uso sistemático de `annotate`, `aggregate` ou `Subquery` para extração de estatísticas pesadas. As somatórias (como no dashboard) são feitas puxando os objetos inteiros do banco e iterando em memória com Python (`sum([adip.tricipital, adip.subescapular...])`), o que é ineficiente comparado a um `aggregate` no Postgres.

====================================================
## 10. TRANSAÇÕES
====================================================

- O projeto usa `with transaction.atomic():` corretamente para garantir integridade.
- **Evidências:** Presente na view `criar_aluno`, `criar_treino`, `criar_avaliacao_idoso` e `criar_avaliacao_crianca`. Se uma falha ocorrer durante a criação encadeada de um modelo e seus atributos, a inserção inteira faz `rollback`, garantindo consistência.

====================================================
## 11. TRATAMENTO DE ERROS
====================================================

- **Tratamento:** Extremamente raso. Faltam blocos nativos de `try/except` robustos na lógica de negócios principal. 
- **Mensagens:** O sistema faz uso pontual de `messages.error(request, ...)` para feedback ao usuário, mas as exceções sistêmicas do banco (como falhas de constraints) não são capturadas de forma limpa, podendo gerar erro 500 (`IntegrityError`).

====================================================
## 12. SEGURANÇA DO BACKEND
====================================================

- **Autenticação:** Baseada no core nativo do Django (`AbstractUser`, `login_required`). 
- **Autorização:** Utiliza decorators criados à parte como `@apenas_personal` e consultas ao usuário via `request.user`. O ORM impõe segurança via tenant scoping: `AvaliacaoFisica.objects.filter(usuario=request.user)`.
- **CSRF:** Middleware de CSRF ativo.

====================================================
## 13. CÓDIGO DUPLICADO
====================================================

- Repetição em lógicas de form e salvamento. 
- O fluxo de criação de objetos `AvaliacaoFisica` + dependências (`Circunferencia`, `Adipometria`) está duplicado pelas views `criar_avaliacao`, `criar_avaliacao_idoso` e `criar_avaliacao_crianca` no arquivo `core/views.py`.

====================================================
## 14. DEPENDÊNCIAS
====================================================

- Dependências entre domínios são gigantes. A View importa mais de 25 elementos em seu cabeçalho (modelos de avaliações misturados com formulários de treino e decoradores de segurança).

====================================================
## 15. CLEAN ARCHITECTURE
====================================================

- **SRP (Responsabilidade Única):** Violado. Modelos e Views acumulam tarefas desconexas.
- **OCP (Aberto/Fechado):** Violado. Inclusões de novos tipos de avaliação exigem modificação do roteamento, de views complexas e inflamento do model único.
- **LSP / ISP / DIP:** A infraestrutura padrão MVC/MTV acoplada do Django não favorece a inversão de dependência (DIP) ou interfaces especializadas. Domínios estão dependentes de instâncias concretas e ORM diretamente na View.

====================================================
## 16. DJANGO BEST PRACTICES
====================================================

- **Faltas notáveis:** Faltam classes `Meta` (verbose_names, defaults, abstract models) consolidadas, ausência de partições em aplicativos (Modular Apps), "Fat Views" ao invés de "Fat Models". O projeto ignorou a documentação de "Best Practices" recomendada da comunidade de usar apps especialistas e Services limitadores de regra.

====================================================
## 17. INTEGRAÇÃO COM A FOUNDATION
====================================================

A Foundation pode agregar valor cirúrgico:
- **`services`:** (Impacto: Alto | Benefício: Isolar lógicas das views, facilitar testabilidade unitária | Dificuldade: Alta, requer reescrita do fluxo de controllers).
- **`utils`:** (Impacto: Médio | Benefício: Padronizar geração de hashes e composição corporal matemática | Dificuldade: Baixa).
- **`validators`:** (Impacto: Médio | Benefício: Melhorar forms de Avaliação Física garantindo consistência em medidas humanas | Dificuldade: Baixa).

====================================================
## 18. PONTOS FORTES
====================================================

- Defesa eficiente contra "N+1" Queries com `select_related` e `prefetch_related`.
- Abordagem transacional robusta com `@transaction.atomic` em fluxos cruciais de inserção.
- Estruturação do `admin.py` é detalhada e rica (`inlines`, `fieldsets`), gerando um bom painel nativo.
- Submódulo extra de `media_pipeline` implementa classes orientadas a serviços (Parser, Scanner).

====================================================
## 19. PONTOS DE ATENÇÃO
====================================================

1. **"Fat Views" (`views.py` inflado e acoplado)** - (Crítico): Dificulta novos deploys e afeta legibilidade.
2. **App "Deus" (`core` monolítico)** - (Crítico): Cria dependências circulares ocultas.
3. **Regras Lógicas em View (IMC, Composições)** - (Alto): Impossibilita reaproveitar cálculos em APIs secundárias ou crons.
4. **Agrupamentos O(N) em memória Python** - (Médio): Iterar dados com arrays em vez de usar `aggregate()` do DB.

====================================================
## 20. OPORTUNIDADES DE REFATORAÇÃO
====================================================

- Particionar o aplicativo `core` em 4 apps primários: `users`, `workouts`, `assessments`, `catalog`.
- Transferir algoritmos matemáticos complexos para classes do domínio. (ex: O cálculo de `percentual` de gordura ser um método abstrato em Service e não ficar solto na rota HTTP).
- Extrair criação de múltiplos Models interligados (Avaliação + Idoso + Medidas) em Factory Services.

====================================================
## 21. EVIDÊNCIAS
====================================================

**Arquivos analisados e caminhos:**
- `c:\Users\Matheus\Desktop\fitflix\core\views.py` (Fat views, regras numéricas soltas)
- `c:\Users\Matheus\Desktop\fitflix\core\models.py` (Classes acopladas sem separação semântica, App Deus)
- `c:\Users\Matheus\Desktop\fitflix\core\urls.py` 
- `c:\Users\Matheus\Desktop\fitflix\projeto\settings.py` (Arquitetura de ambiente)
- `c:\Users\Matheus\Desktop\fitflix\core\admin.py`
- `c:\Users\Matheus\Desktop\fitflix\core\forms.py`

====================================================
## 22. ESTATÍSTICAS
====================================================

- **Número de apps:** 1 (`core`) de negócios
- **Número de models:** 13 (incluindo models base e dependentes)
- **Número de views:** ~18-20 funções tratadoras HTTP
- **Número de forms:** 9 formulários principais (com mix de inlines)
- **Número de management commands:** Pelo menos 3 principais
- **Número de services abstratos:** 2 explícitos
- **Número de utils gerais:** 2
- **Maior arquivo de código:** `core/views.py` (~820 linhas)
- **Módulos com maior responsabilidade:** O app `core` e especificamente `views.py`.

====================================================
## 23. PRIORIZAÇÃO
====================================================

| Problema | Impacto | Complexidade | Prioridade |
| --- | --- | --- | --- |
| "Fat Views" e Regras de Negócio na UI | Crítico | Média | P1 |
| Desmembramento do "App Deus" | Alto | Alta | P2 |
| Delegação do processamento matemático (`sum()`) para Aggregate DB | Médio | Baixa | P3 |
| Implementação de camada Service robusta | Alto | Alta | P1 |

====================================================
## 24. NOTA GERAL
====================================================

- **Organização:** 3/10 (Concentração exagerada num único local raiz).
- **Legibilidade:** 6/10 (Pythonic e com boa quebra de formatação, porém prolixo nas views).
- **Modularidade:** 2/10 (Componentes altamente acoplados).
- **Escalabilidade:** 4/10 (Escala em nuvem via ORM, mas codebase frágil a escalada de time).
- **Segurança:** 7/10 (Aproveita bem os sistemas default robustos do Django e queries seguras).
- **Aderência ao Django:** 5/10 (Segue padrões MTV primários, falha em seguir padrão "Pluggable Apps").
- **Qualidade Geral:** 5/10 


# Auditoria Complementar - Deep Analysis Backend

=========================================================
## 1. MODELS (ANÁLISE COMPLETA)
=========================================================

### Domínio de Usuários
- **`Usuario`**: Estende `AbstractUser`. Responsabilidade: Autenticação e Perfis (Admin, Personal, Aluno).
  - *Tamanho:* Pequeno (~20 linhas).
  - *Qualidade:* Média. O model mistura atributos nativos com `cref`, `telefone` e `tipo_usuario`. Deveria existir um `Perfil` (OneToOne) ou isolamento maior.
  - *Coesão:* Baixa (mistura credencial e dados profissionais no mesmo schema).

### Domínio de Avaliações
- **`AvaliacaoFisica`**: Modelo central do paciente/aluno.
  - *Responsabilidade:* Dados base de antropometria.
  - *Qualidade:* Possui properties úteis (`idade`, `imc`), o que indica lógica no lugar certo. No entanto, o `imc` usa um `try/except` vazio capturando tudo silenciosamente, o que é um anti-pattern (*Code Smell* em `models.py`, linha 80).
- **`Circunferencia` / `Adipometria` / `AvaliacaoCrianca` / `AvaliacaoIdoso`**: Extensões da AvaliaçãoFisica através de `OneToOneField`.
  - *Qualidade da modelagem:* **Excelente**. Evita uma única tabela absurdamente larga (com dezenas de colunas nulas) através do particionamento correto (Normalização via OneToOne).
  - *Atributos:* Faltou apenas o uso de `related_name` mais padronizados, mas `related_name="circunferencias"` e `"adipometria"` estão presentes.

### Domínio de Treinos e Catálogo
- **`Treino` e `ExercicioTreino`**: Agrupam a montagem do treino.
  - *Relacionamentos:* Utilizam `ForeignKey` com on_delete=CASCADE e possuem `related_name="exercicios"`. Estão bem modelados do ponto de vista de chaves estrangeiras.
- **`VideoExercicio` e `VariacaoExercicio`**: Acoplamento fortíssimo com `GrupoMuscular`.
  - *Risco:* Estão misturados no app principal. `VariacaoExercicio` tem uma FK para `GrupoMuscular` nula (`on_delete=models.SET_NULL`). 
  
### Diagnóstico Geral
**A modelagem em si não é ruim estruturalmente (chaves estrangeiras corretas, tipos de dados adequados). O problema central é a ausência de divisão em múltiplos aplicativos ("App Deus").** A grande maioria dos modelos são *modelos anêmicos* (só possuem campos, não possuem métodos de negócio). Exceção à classe `AvaliacaoFisica` (que possui `imc` e `idade`). Faltou o uso sistêmico da classe `Meta` (verbose_name, ordering).

=========================================================
## 2. SERVICES
=========================================================

Os serviços do sistema estão escassos na camada web, mas muito bem elaborados no pipeline offline.

- **`core/email_service.py`**:
  - *Responsabilidade:* Abstrair o disparo de email via `send_mail`.
  - *Padrão:* Função utilitária (*Helper* mais do que uma classe de domínio).
  - *Isolamento:* Correto. Evita poluir a view com formatação de strings do corpo de email.
- **`core/media_pipeline/` (Submódulo Service)**:
  - Aqui existe uma estrutura **excelente** orientada a Serviços de Domínio.
  - Classes como `Parser`, `Scanner`, `Auditor`, `Matcher`, `Builder`.
  - *Responsabilidade:* Processar, auditar e vincular os GIFs do catálogo.
  - *Padrão:* Single Responsibility Principle total. O scanner apenas escaneia, o matcher aplica regras Heurísticas de matching string e o auditor valida. 
- **`core/services/fitflix_persister.py`**:
  - *Responsabilidade:* Persistir resultados em lote. (Evidência: Classe com método `persister` que recebe instâncias iteráveis).
  - *Qualidade:* Acabou abandonado/incipiente (código possui blocos `continue` sem muita validação).

**Onde estão as regras de negócio reais?**
Elas permanecem na View (`core/views.py`). O `calcular_composicao()` na linha 353 e a criação de múltiplas avaliações conjuntas na view provam que o padrão Service na Web foi completamente negligenciado.

=========================================================
## 3. FORMS
=========================================================

- **Uso do ModelForm:** O projeto utiliza amplamente `forms.ModelForm`, alinhado com o framework. (ex: `AvaliacaoFisicaForm`, `AdipometriaForm`).
- **Validações `clean()` e `clean_<campo>()`**:
  - Utilizado inteligentemente no `TreinoForm` (linha 161) validando a existência mutualmente exclusiva do aluno.
  - No `CriarAlunoForm` o método `clean_email()` (linha 255) verifica duplicação via ORM (`User.objects.filter(...)`). **Excelente prática.**
- **Injeção de CSS em Forms**:
  - Em `TreinoForm` (linha 145) e `CriarAlunoForm` (linha 250), o form itera em `self.fields.items()` injetando as classes CSS `treino-input` e `input-field`.
  - *Diagnóstico:* Isso é uma má prática. Front-end CSS e formatação visual (Classes Bootstrap/Tailwind) deveriam ser aplicados no Template HTML (através de bibliotecas como `django-widget-tweaks` ou `crispy-forms`) e não codificados duramente no core Python (Backend).
- **Reutilização e Herança**: Não existe herança de Forms base. Todos reescrevem as injeções repetidamente, gerando código duplicado.

=========================================================
## 4. SEGURANÇA
=========================================================

- **Login e Decorators:** O backend faz uso massivo de `@login_required` para trancar acessos anônimos e possui o decorator customizado `@apenas_personal` para autorização vertical em views sensíveis (`criar_aluno`, `adicionar_exercicio`). Isso é adequado.
- **Tenant Isolation (Multi-tenant via ORM):** Correto.
  - *Evidência:* Na view `detalhe_avaliacao` há verificação segura: `get_object_or_404(AvaliacaoFisica, id=id, usuario=request.user)`. O ID inserido na URL jamais deixará que o usuário A veja a avaliação do usuário B.
- **CSRF:** O `CsrfViewMiddleware` está em `settings.py`. Como as views dependem do `forms.Form`, a validação de token é automática e obrigatória por design.
- **Env e Secrets:**
  - `SECRET_KEY` resgatada através de `os.environ.get("SECRET_KEY")`. Correto.
  - `DEBUG` está estaticamente configurado como `True` (linha 21). *Risco de segurança crítico em Produção* (vaza Call Stacks completas).
- **ALLOWED_HOSTS:** Trancado para `"avaliacao-fisica-saas.onrender.com"` e localhost. Correto para evitar DNS rebinding attacks.
- **Cloudinary Storage:** Credenciais não estão comitadas duras, usam `os.getenv`.
- **Uploads de Arquivos:** Vulnerável. O model `VideoExercicio` aceita qualquer tipo de `FileField` (linha 245) ou `gif` sem restrições ou validadores de mimetype/extensão. Um usuário mal intencionado no painel admin poderia enviar scripts `.sh` ou `.exe` mascarados.

=========================================================
## 5. DEPENDÊNCIAS EXTERNAS
=========================================================

- `Django==5.1` (Framework Core)
- `cloudinary==1.44.2` e `django-cloudinary-storage==0.3.0` (Para salvar as mídias externamente em Nuvem). *Fundamental; a alternativa seria S3 (boto3).*
- `dj-database-url==2.1.0` (Para converter a variável DATABASE_URL em dicionários estruturados do Django. Ótimo padrão SaaS).
- `psycopg` e `psycopg2-binary` (Drivers para conexão no PostgreSQL hospedado).
- `whitenoise==6.11.0` (Para servir arquivos estáticos em produção diretamente do gunicorn, evitando precisar de um NGINX configurado a mão na nuvem).
- `pillow==12.2.0` (Tratamento interno de imagens nos campos ImageField/FileField, útil, mas talvez overkill dado que os arquivos são salvos diretamente no Cloudinary).
- `python-dotenv` (Gestor de credenciais e senhas da API locais).

=========================================================
## 6. MANAGEMENT COMMANDS
=========================================================

- *Localização:* `core/management/commands/`.
- **`upload_gifs_cloudinary.py`**:
  - *Objetivo:* Sincronizar GIFs de variação do disco local para o Cloudinary em nuvem.
  - *Qualidade:* Robusto. Usa paginação/controles avançados, mas possui 7948 bytes, sendo um arquivo demasiadamente complexo e acoplado logicamente à API externa.
- **`vincular_gifs.py`**:
  - *Objetivo:* Conectar entradas órfãs baseando-se em nomes similares.
  - *Risco:* Baixo. É apenas administrativo.
- **`migrar_sqlite_para_postgres.py`**:
  - *Objetivo:* Fazer dumping local para injetar em produção.
  - *Código Duplicado / Qualidade:* Este comando lida com raw queries (SQL bruto), o que foge bastante das boas práticas de portabilidade ORM (foge da abstração via `dumpdata`/`loaddata` nativa do Django).

=========================================================
## 7. ESTATÍSTICAS REAIS
=========================================================

- **Número de apps:** 1 app de negócio funcional (`core`).
- **Número de models:** 13.
- **Número de forms:** 9 formulários principais (com mix de inlines auxiliares).
- **Número de views:** 17 rotas apontando para funções ativas (`views.py`).
- **Número de templates:** 36 arquivos `.html` mapeados.
- **Número de urls:** 19 entradas no array `urlpatterns`.
- **Número de services:** 13 (2 na web, ~11 no submódulo `media_pipeline`).
- **Número de utils:** 3.
- **Número de management commands:** 15 scripts (ex: `upload_gifs_cloudinary`, `scan_midias`, `migrar_gif`).
- **Número de migrations:** 9 arquivos na subpasta `core/migrations`.
- **Número de testes:** 3 arquivos (`tests.py`, `media_pipeline/tests.py`, `test_catalog.py`).
- **Número de arquivos Python (total s/ venv):** 68.

**Top 10 maiores arquivos Python (Por tamanho em disco):**
1. `core/views.py` (21.2 KB)
2. `core/migrations/0001_initial.py` (20.5 KB)
3. `core/forms.py` (9.8 KB)
4. `core/models.py` (9.2 KB)
5. `core/tests.py` (8.4 KB)
6. `core/management/commands/upload_gifs_cloudinary.py` (7.9 KB)
7. `core/management/commands/seed_exercicios.py` (7.0 KB)
8. `popular_variacao.py` (Script Sujo, 5.3 KB)
9. `projeto/settings.py` (5.1 KB)
10. `core/admin.py` (4.9 KB)

=========================================================
## 8. DÍVIDA TÉCNICA
=========================================================

| Problema | Arquivo | Impacto | Complexidade | Prioridade | Justificativa |
| --- | --- | --- | --- | --- | --- |
| `DEBUG = True` chumbado em Produção | `projeto/settings.py` | Crítico | Baixa | P1 | Riscos graves de exposição de infraestrutura e vazamento de env vars em tela de erro. |
| Injeção CSS (Classes front) via classe em Python | `core/forms.py` | Baixo | Média | P3 | Quebra a responsabilidade do Frontend, forçando o programador de HTML ir no Python mudar estilo. |
| Funções sem Handler de Erros (`except: pass`) no ORM e Modelos | `core/models.py`, `views.py` | Médio | Baixa | P2 | Exceções genéricas engolidas que gerarão debug complexo em produção caso ocorram falhas de banco. |
| Script Sujos e Lixo na Raiz | raiz do projeto (`popular*.py`) | Baixo | Baixa | P3 | Poluição do repositório, scripts que deveriam ser *management commands* e não estar na base do git. |
| Falta de Validador Mime Type em Arquivos | `core/models.py` | Alto | Baixa | P2 | Upload irrestrito ao Cloudinary. Falha de segurança primária (File Upload Vulnerability). |

=========================================================
## 9. EVIDÊNCIAS
=========================================================

- **Acoplamento Models:** O arquivo `core/models.py` agrupa os domínios `AvaliacaoFisica` (linha 38) com `VideoExercicio` (linha 240) comprovando a existência técnica de um Monolito (App Deus).
- **Regras Matemáticas Soltas:** O cálculo numérico de proporções antropológicas está implementado fora de um método de classe, na solta função `calcular_composicao()` no arquivo `core/views.py` (linha 353).
- **Exceção Vazia / Silenciosa (Anti-Pattern):** Em `core/models.py` linha 80 na property `@property imc(self):`, há um bloco `except: return None` que captura desde um erro de divisão por zero até um syntax error vital da VM.
- **Injeção imperativa de estilos CSS:** Localizada no form de `core/forms.py` linha 152: `field.widget.attrs["class"] = f"{existing_class} {field_classes}".strip()`.

=========================================================
## 10. CONCLUSÃO
=========================================================
O Fitflix não precisa ser reescrito.

A auditoria mostra que a maior parte dos problemas está concentrada na organização da lógica, não na tecnologia escolhida nem na modelagem principal. O projeto demonstra conhecimento técnico consistente (ORM, transações, integração com Cloudinary, PostgreSQL e um pipeline de mídia bem estruturado), mas evoluiu de forma incremental, resultando em concentração de responsabilidades em alguns módulos. A estratégia mais promissora é uma refatoração gradual, guiada pela Foundation, preservando o que já funciona e extraindo responsabilidades aos poucos, em vez de promover uma reestruturação radical.
