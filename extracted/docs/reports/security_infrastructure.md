# Auditoria Definitiva - Infraestrutura, Segurança e PostgreSQL

=========================================================
## 1. RESUMO EXECUTIVO
=========================================================
A infraestrutura e a postura de segurança do Fitflix denotam um ambiente **MVP de alto risco**. Embora conte com provedores robustos (Render, Cloudinary e PostgreSQL) e fundações do Django (ORM blindado contra SQL Injection), a configuração da camada web expõe a aplicação a vazamentos críticos de dados em produção e sequestros de sessão.
A **maturidade** de segurança é muito baixa. Há ausência completa de endurecimento (Hardening) de cookies, HSTS e headers de segurança HTTP. A **exposição** é alta devido à manutenção do `DEBUG = True` em nuvem pública (Render). A infraestrutura de *deploy* foi modelada para rodar rápido, sacrificando políticas de *Least Privilege* e *Zero Trust*.

=========================================================
## 2. AUDITORIA DO POSTGRESQL
=========================================================
- **ENGINE:** `dj_database_url` configurado para instanciar as conexões baseadas na variável `DATABASE_URL` (Postgres hospedado na nuvem).
- **SSL:** `ssl_require=False` configurado expressamente em `settings.py` (linha 99). *Crítico:* A comunicação entre o worker do Django e o Banco Postgres ocorre em texto plano se trafegar por redes externas ao cluster.
- **Pooling / Conexões:** `conn_max_age=600` ativado. *Positivo:* Mantém a conexão aberta no backend por 10 minutos, o que reduz custos de handshake TCP/SSL nas requisições. 
- **Transactions / Autocommit:** O Django opera em modo autocommit por default. Não há alteração explícita (como `ATOMIC_REQUESTS = True`).
- **Timeouts:** Não há configurações explícitas para `options: {"connect_timeout": X}` no `settings.py`, deixando o projeto à mercê dos defaults de rede, propiciando travamentos de Gunicorn (*Worker Timeout*).
- **Timezone / Encoding:** `TIME_ZONE = "America/Sao_Paulo"` (linha 135) com `USE_TZ = True`. *Positivo*.
- *Não foi possível determinar através da análise do projeto:* Isolamento físico, locks, vacuum, e buffers de memória (Shared Buffers, Work Mem), pois essas parametrizações pertencem ao provedor Cloud (Render PostgreSQL managed database) e não ao repositório Django.

=========================================================
## 3. CONFIGURAÇÃO DJANGO
=========================================================
Análise técnica do arquivo `projeto/settings.py`:
- **DEBUG:** `True` (linha 21). **Vulnerabilidade gravíssima em produção**.
- **SECRET_KEY:** Salva de forma segura no ambiente (`os.environ.get("SECRET_KEY", "dev-secret-key")`). Contudo, o fallback gera risco caso a variável não seja lida em prod.
- **ALLOWED_HOSTS:** `["avaliacao-fisica-saas.onrender.com", "127.0.0.1", "localhost"]`. *Positivo.* Evita Host Header Injection.
- **CSRF_TRUSTED_ORIGINS:** Preenchido para domínios Render.
- **SECURE_PROXY_SSL_HEADER:** `("HTTP_X_FORWARDED_PROTO", "https")` configurado, ajudando no roteamento do SSL.
- **O QUE FALTA (Não configurado / Padrão inseguro):**
  - `SECURE_SSL_REDIRECT`: Ausente. (O site pode ser acessado via HTTP puro).
  - `SECURE_HSTS_SECONDS`: Ausente. (O navegador não forçará HTTPS).
  - `HSTS_INCLUDE_SUBDOMAINS` / `HSTS_PRELOAD`: Ausentes.
  - `SECURE_CONTENT_TYPE_NOSNIFF`: Ausente.
  - `SECURE_BROWSER_XSS_FILTER`: Ausente.
  - `SECURE_REFERRER_POLICY`: Ausente.
  - `SESSION_COOKIE_SECURE`: Ausente (Cookies de login viajam em HTTP texto plano se não houver redirect).
  - `CSRF_COOKIE_SECURE`: Ausente.

=========================================================
## 4. MIDDLEWARE
=========================================================
Ordem (linha 48):
1. `SecurityMiddleware` (Correto, primeiro a rodar).
2. `WhiteNoiseMiddleware` (Correto para arquivos estáticos).
3. `SessionMiddleware`
4. `CommonMiddleware`
5. `CsrfViewMiddleware` (Fundamental).
6. `AuthenticationMiddleware` (Correto, apóso Session).
7. `MessageMiddleware`
8. `XFrameOptionsMiddleware` (Previne *Clickjacking* via iFrames).
- **Avaliação:** Ordem correta, sem duplicações. Faltam middlewares de `Rate Limiting` (ex: django-ratelimit), deixando a aplicação vulnerável a *Brute Force* no login.

=========================================================
## 5. AUTENTICAÇÃO
=========================================================
- **Modelo Base:** `AUTH_USER_MODEL = "core.Usuario"` estendendo `AbstractUser`. O hash nativo (PBKDF2) é robusto.
- **Password Validators:** `AUTH_PASSWORD_VALIDATORS` configurados por padrão (Similarity, MinimumLength, CommonPassword, NumericPassword). *Positivo*.
- **Timeout Session:** Ausente. Não foi localizado `SESSION_COOKIE_AGE`, o que significa que se um computador for deixado ligado, o token de sessão do usuário/personal fica ativo por padrão (14 dias).

=========================================================
## 6. AUTORIZAÇÃO
=========================================================
- **Escalada de Privilégios / IDOR (Insecure Direct Object Reference):** O sistema está **PARCIALMENTE PROTEGIDO**. 
- *Evidência Positiva:* Em views críticas (`detalhe_avaliacao`), existe blindagem no ORM utilizando `.filter(usuario=request.user)`. 
- *Risco Latente:* Em formulários (`TreinoForm` / `AvaliacaoFisicaForm`), se as QuerySets dos campos `ModelChoiceField` (ex: lista de Alunos) não forem filtradas no método `__init__` via `self.user`, um personal pode forçar o ID de um aluno que pertence a outro personal via *Inspect Element* (Burp Suite), ocasionando escalada horizontal. 

=========================================================
## 7. OWASP TOP 10
=========================================================
- **A01: Quebra de Controle de Acesso (Broken Access Control):** *Parcialmente Protegido*. Existem os decorators `@login_required` e `@apenas_personal`, mas formulários soltos e limites de IDOR nas FKs merecem atenção.
- **A02: Falhas Criptográficas:** *Vulnerável*. Ausência de `SESSION_COOKIE_SECURE` e HSTS permite interceptação de sessão via redes públicas (Man-in-the-Middle).
- **A03: Injeção (SQL Injection):** *Protegido*. O sistema baseia-se 100% nas proteções de escape do Django ORM, sem raw queries nas views web.
- **A04: Design Inseguro:** *Parcialmente Protegido*. Ausência de captcha e rate-limits em rotas sensíveis (Login/Register).
- **A05: Desconfiguração de Segurança:** *Vulnerável Crítico*. O `DEBUG = True` acionado.
- **A06: Componentes Vulneráveis:** *Protegido* (Django 5.1 é a versão mais moderna até a data).
- **A07: Falha de Identificação e Autenticação:** *Vulnerável*. Cookies sem endurecimento completo.
- **A08: Falha na Integridade de Software:** *Não foi possível determinar através da análise do projeto* (Depende da CI/CD no Render).
- **A09: Monitoramento Insuficiente:** *Vulnerável*. O projeto não tem integração de logs robusta, Sentry ou fail2ban configurados.
- **A10: Falsificação de Requisição do Servidor (SSRF):** *Protegido* (Não baixa assets externos não controlados nas views web).

=========================================================
## 8. UPLOADS
=========================================================
- O model `VideoExercicio` em `core/models.py` abriga mídias hospedadas remotamente, além disso há scripts como `upload_gifs_cloudinary.py`.
- **Validação de Extensão / Mimetype:** Inexistente no Model. 
- **Zip Bomb / Scripts maliciosos:** *Vulnerável*. Qualquer arquivo renomeado pode ser feito upload no Django Admin. A salvação acidental é que o Cloudinary (que recebe e serve as mídias) possui firewalls nativos pesados que ignoram execução de SVG com Javascript embutido, mas o backend Django é um pass-through vulnerável (salva lixo inútil no banco).

=========================================================
## 9. SQL INJECTION
=========================================================
- **ORM / Raw SQL:** Não foram encontrados trechos com `.raw()`, `.extra()`, ou execução crua de `cursor.execute()` nos módulos web (`views.py`). O projeto utiliza 100% de consultas paramétricas nativas do Django, isolando completamente ataques de Injeção via Input Textual. 
- *Protegido.*

=========================================================
## 10. XSS (Cross-Site Scripting)
=========================================================
- **Templates:** O Django aplica *Autoescaping* nas renderizações de string como `{{ variavel }}`.
- **Javascript Inline:** *Parcialmente Vulnerável*. No `dashboard.html` (linha 214) temos injeção explícita de valor de template no meio do script local `parseFloat('{{ composicao.massa_gorda|default:"0" }}')`. Se essa variável vier suja e sem o `float` parser, quebra o JS da página. Não é XSS estrito (são floats), mas a prática é vetor para falhas em campos string (Reflected XSS). Não há indício do uso da flag `|safe` indevidamente.

=========================================================
## 11. CSRF (Cross-Site Request Forgery)
=========================================================
- *Protegido*. O `CsrfViewMiddleware` (settings.py linha 53) está configurado. Como os templates dependem da API do Django para forms (`{% csrf_token %}` em POST), ataques trans-site em formulários submetidos falharão com HTTP 403 Forbidden.

=========================================================
## 12. CORS (Cross-Origin Resource Sharing)
=========================================================
- *Não configurado.* O pacote `django-cors-headers` não está listado em `INSTALLED_APPS` nem em `MIDDLEWARE`. Se a API REST for habilitada no futuro, ela bloqueia requisições cross-domain (o default do browser limitará via Same-Origin-Policy). Como é um SSR clássico, a falta dele protege os endpoints no cenário atual.

=========================================================
## 13. COOKIES E SESSÕES
=========================================================
- O `django.contrib.sessions` opera os cookies. 
- O endurecimento das flag `Secure` e `HttpOnly` está negligenciado no `settings.py`. Como o domínio é HTTPS no Render, seccionar isso via `SESSION_COOKIE_SECURE = True` é fundamental para anular ataques via redes wifi públicas interceptadas.

=========================================================
## 14. CLOUDINARY
=========================================================
- **Configuração:** `CLOUDINARY_STORAGE` configurado com `CLOUD_NAME`, `API_KEY`, e `API_SECRET` lidos do ambiente estritamente via `os.getenv()`. (settings.py, linhas 213-219).
- **Segurança:** O parâmetro `SECURE: True` está setado, forçando URLs de mídia com HTTPS, blindando Mixed Content em frontends criptografados. *Positivo*.

=========================================================
## 15. RENDER / DEPLOY
=========================================================
- O ambiente na nuvem injeta `DATABASE_URL` e as secret keys. 
- **Build / Logs:** A presença de `gunicorn==25.1.0` e `whitenoise==6.11.0` no `requirements.txt` formata um ambiente compatível com os contêineres e Buildpacks do Render.
- Contudo, **DEBUG = True** (settings.py linha 21) é um erro clássico e crasso. O render rodará em modo dev, servirá páginas de erro amarelas com env_vars visíveis aos hackers (dump de variáveis locais) no menor sinal de Exception Web (ex: erro no cálculo de `massa_magra`).

=========================================================
## 16. DEPENDÊNCIAS
=========================================================
- Django 5.1 (Framework).
- psycopg 3.3.2 (Compatível com PostgreSQL 12+).
- *Vulneráveis?* As versões não estão congeladas no passado obsoleto, tratam-se das versões mais recentes disponíveis em 2024/2025. 
- *Desnecessárias?* O uso concomitante de `psycopg` e `psycopg2-binary` no `requirements.txt` pode gerar conflito em ambientes de deploy enxuto no linux e só consome peso inútil em imagens Docker/SlugSize.

=========================================================
## 17. POSTGRESQL PERFORMANCE
=========================================================
- *Não foi possível determinar através da análise do projeto* detalhes do Planner, Parallel Queries, EXPLAIN ANALYZE ou uso de Bitmap Scans. 
- **Justificativa:** O código fonte apenas dita as querysets da ORM. Análises de plano de execução (Explain) e buffers requerem o console do banco rodando uma amostra de carga com `pg_stat_statements` ativado no Cloud SQL (Render).

=========================================================
## 18. PENETRATION TEST READINESS
=========================================================
O projeto **NÃO** está pronto para ser exposto a um Pentest corporativo severo. Falharia quase de imediato nas fases automatizadas de varredura.
**Vetores principais a testar (se for feito):**
1. Testar o Cookie sem flag SECURE interceptando a rede web.
2. Forçar Exceptions gerando URL não mapeada ou divisão por zero em formulários, pra forçar o `DEBUG = True` renderizar a stack trace.
3. Avaliar falha de Upload via painel enviando Scripts renomeados por `.gif`.
4. Mass-assignment / IDOR nas trocas de IDs nos *Hidden fields* de avaliação física.

=========================================================
## 19. EVIDÊNCIAS
=========================================================
- **Exposição:** `projeto/settings.py` linha 21: `DEBUG = True`.
- **SSL Fragilizado:** `projeto/settings.py` linha 99: `ssl_require=False`.
- **Credenciais Seguras:** `projeto/settings.py` linha 213: Uso constante de `os.getenv` blindando o repositório contra chaves vazadas.
- **Injeção de JS:** `core/templates/core/dashboard.html` linha 214: `parseFloat('{{ composicao.massa_gorda|default:"0" }}')`.

=========================================================
## 20. ESTATÍSTICAS
=========================================================
- Middlewares: 8.
- Decorators Seguros: `@login_required` acoplado nas views protegidas.
- Models Sensíveis: `Usuario`, `AvaliacaoFisica` (Armazenam dados antropométricos sensíveis sob LGPD/HIPAA).
- Uploads: Arquivos centralizados via módulo unificado Cloudinary Storage.
- Settings de Segurança Críticos Ativados: 2 (`ALLOWED_HOSTS`, `SECURE_PROXY_SSL_HEADER`).
- Settings de Segurança Faltantes: > 8.

=========================================================
## 21. DÍVIDA TÉCNICA
=========================================================

| Problema | Arquivo | Impacto | Complexidade | Prioridade | Justificativa |
| --- | --- | --- | --- | --- | --- |
| DEBUG ativado em produção | `settings.py` | Crítico | Baixa | P1 | Risco gigantesco de Data Leak (Source Code e Envs) na internet através da Traceback amarelinha do Django. |
| Inexistência de Hardening nos HTTP Cookies e HSTS | `settings.py` | Alto | Baixa | P1 | Sem flags HTTPOnly/Secure e HSTS, a sessão trafega em texto claro, vulnerável a sniffing de rede. |
| PostgreSQL SSL desativado no Driver | `settings.py` | Médio | Baixa | P2 | Risco dependente da rede do Render, mas o ideal é tunelar toda conexão (sslmode=require). |
| Ausência de limites no Arquivo de Upload | `models.py` | Alto | Média | P2 | Falta de validador de cabeçalho mágico de Mime Type no Django Models permitindo arquivos espúrios. |

=========================================================
## 22. PONTOS FORTES
=========================================================
- Nenhuma chave secreta vazou no código fonte. Todos os provedores são declarados via ambiente local `.env`.
- Base unicamente confiada ao ORM do Django, zerando completamente o vetor de injeção SQL nas queries transacionais.
- Roteamento HTTPS para os assets (Mídias do Cloudinary com HTTPS forçado em flag local).

=========================================================
## 23. PONTOS DE ATENÇÃO
=========================================================
- **Crítico:** DEBUG = True na branch principal que sobe pro deploy (Render).
- **Alto:** Sessões abertas permanentemente, vazando pelo ar (Cookies não seguros).
- **Médio:** Injeção solta de template vars num HTML inline Javascript.
- **Médio:** Dependências cruas no banco que dificultam deploys lean (duas bibliotecas psycopg concorrentes no `requirements.txt`).

=========================================================
## 24. COMPATIBILIDADE COM A FOUNDATION
=========================================================
O módulo de Foundation poderia fechar todas essas vulnerabilidades implementando:
- **Config / Security:** Centralizar a leitura de variáveis `.env` e forçar uma chave de *Security Hardening* acionando `SECURE_SSL_REDIRECT = not DEBUG`, `SECURE_HSTS_SECONDS = 31536000`, e flags de cookies (Secure/HttpOnly) através de um arquivo `core_settings.py` protegido da mutação acidental por desenvolvedores Júniores.
- **Validators:** Uma camada abstrata de validação MimeType para extirpar uploads perigosos antes mesmo de encostar no conector do Cloudinary.
- **Rate Limit:** Acoplar decorators limitadores de Request/IP na tela de Autenticação (`login`) barrando Brute-forces.
- **Observabilidade:** Conectar automaticamente Sentry.io para gerenciar exceptions anonimizadas no lugar da estúpida página de DEBUG do Django.

=========================================================
## 25. NOTA GERAL
=========================================================
- **Segurança:** 3/10 (Falha crítica na tela de DEBUG e hardening de pacote HTTP zerado).
- **PostgreSQL:** 6/10 (Conexões ativas, uso de pooler local e suporte transacional, mas peca na exposição e índice).
- **Deploy:** 7/10 (Feito pensando 100% em infra Cloud Modern SaaS - Gunicorn/Whitenoise - apesar da config).
- **Infraestrutura:** 7/10 (Boa segmentação de discos - Cloudinary pra media, Postgres em Server, Django em app dyno).
- **Autenticação:** 6/10 (Nativa, robusta, mas desprotegida por cookies HTTP soltos).
- **Autorização:** 5/10 (Depende dos decorators, mas expõe IDOR em combobox HTML de formulários não-filtrados).
- **Hardening:** 1/10 (Desprezado no `settings.py`).
- **Escalabilidade:** 6/10 (Sem chaves gargalo no backend nativo, porém faltam os limiters, caches em disco/redis e poolers corporativos como PgBouncer).

=========================================================
## 26. CONCLUSÃO
=========================================================
A infraestrutura em nuvem e a camada de segurança do projeto Fitflix exibem o retrato clássico do *Fast-Delivery* (Entrega Rápida) no qual a infra é provisionada com sucesso operacional, porém com segurança zero baseada em boas práticas de *Post-Production*. 
Exposto e operando com `DEBUG = True` ao mundo, o Django se transforma numa mina terrestre armada para vazamentos corporativos ao menor deslize de tipagem de dados. A adoção de plataformas consolidadas de *Cloud* (Render) e *Storage* (Cloudinary), operadas via bibliotecas (WhiteNoise e Gunicorn), provam que a arquitetura moderna (*12-Factor App*) está dominada. Entretanto, a aplicação precisa passar urgentemente por uma repaginada nas variáveis e flags do `settings.py` (Cookies Seguro, HSTS, Proxy headers) e no acoplamento da API do Cloudinary para fechar as vulnerabilidades frontais do *OWASP Top 10* antes de enfrentar audições e escalar contas reais de pacientes sob compliance de saúde.
