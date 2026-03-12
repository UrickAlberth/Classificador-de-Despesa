# Sistema IA de Classificação de Despesa (TJMG) - MVP

MVP em Python com FastAPI para classificação econômica da despesa e apoio tributário, usando:

- Base CATMAS/SIAD via Google Sheets (com fallback CSV local);
- Tabelas orçamentárias (XLSX) com foco em Tabelas 3, 4, 5, 7 e 8;
- Documentos do processo SEI 0038700-03.2026.8.13.0000 como contexto de conhecimento;
- Integração de IA com OpenAI (gpt-4.1-mini) ou Azure OpenAI via chave de API.
- Vetorização da base CATMAS em SQLite com embeddings text-embedding-3-large.

## Requisitos cobertos

1. **Fontes de dados e base de conhecimento**
   - Carrega CATMAS, classificador e tabelas orçamentárias locais.
   - Carrega e resume anexos PDF/HTML do processo SEI para contexto.
   - Integração externa com IBGE (CNAE) implementada.
   - Integração externa com NFS-e preparada por `NFSE_NACIONAL_BASE_URL`.

2. **Insumos (Input)**
   - Endpoint recebe `finalidade` e `objeto_contratacao` como centrais.
   - Campo opcional `texto_documentos` para conteúdo extraído de CI, Pedido SIAD, ETP, TR, Contrato.

3. **Regras de negócio**
   - Cruzamento obrigatório: Finalidade x Objeto x Tabelas Orçamentárias.
   - Verificação de status CATMAS priorizando itens `ATIVO`.
   - Suporte a múltiplas sugestões (`max_sugestoes`).
   - Verificação preliminar de compatibilidade CNAE (CNPJ/CNAE informado x IBGE).

4. **Saídas obrigatórias**
   - Item CATMAS.
   - Categoria Econômica (Tabela 3).
   - Grupo de Natureza da Despesa (Tabela 4).
   - Modalidade de Aplicação (Tabela 5).
   - Elemento de Despesa (Tabela 7).
   - Item de Despesa (Tabela 8).
   - Código de Tributação Nacional (quando integração estiver disponível).

5. **Conformidade e riscos**
   - Retorna alinhamento com Lei 14.133/2021 e Resolução CNJ 370/2021.
   - Emite alertas para risco de inconsistência tributária.

## Estrutura

- `app/main.py`: API FastAPI.
- `app/schemas.py`: modelos de entrada/saída.
- `app/data_sources.py`: ingestão e busca nas bases.
- `app/external_integrations.py`: consultas IBGE/NFS-e.
- `app/gemini_client.py`: integração OpenAI (chat + fallback).
- `app/service.py`: orquestração e regras de negócio.
- `frontend/`: aplicação React para operação do fluxo com painel de andamento.

## Como executar

1. Crie `.env` a partir de `.env.example` e preencha:
    - `AI_PROVIDER=openai` (padrão) ou `AI_PROVIDER=azure`
    - Se `openai`:
       - `OPENAI_API_KEY`
       - `OPENAI_CHAT_MODEL` (default `gpt-4.1-mini`)
       - `OPENAI_EMBEDDING_MODEL` (default `text-embedding-3-large`)
    - Se `azure`:
       - `AZURE_OPENAI_API_KEY`
       - `AZURE_OPENAI_ENDPOINT` (ex.: `https://seu-recurso.openai.azure.com`)
       - `AZURE_OPENAI_API_VERSION` (default `2024-10-21`)
       - `AZURE_OPENAI_CHAT_DEPLOYMENT` (nome do deployment do chat)
       - `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` (nome do deployment de embeddings)
   - `ENABLE_CATMAS_VECTOR_SEARCH=true`
   - `ENABLE_CATMAS_VECTOR_SYNC_ON_STARTUP=false` (recomendado em App Service)
   - `CATMAS_VECTOR_DB_PATH=/home/data/catmas_vectors.db` (recomendado em App Service Linux)
   - `ENABLE_EXTERNAL_LOOKUPS=true` (para habilitar consultas online)
   - `CATMAS_GOOGLE_SHEETS_URL` (opcional, padrão aponta para a planilha oficial)
   - opcional: `NFSE_NACIONAL_BASE_URL`

2. Instale dependências:

```bash
pip install -r requirements.txt
```

3. Suba a API:

```bash
uvicorn app.main:app --reload
```

4. Teste:

```bash
curl -X POST http://127.0.0.1:8000/analisar \
  -H "Content-Type: application/json" \
  -d '{
    "finalidade": "Contratação de serviço de hospedagem de sistema de biblioteca",
    "objeto_contratacao": "Serviço de hospedagem, migração e suporte técnico continuado do sistema Pergamum",
    "cnae_empresa": "6204-0/00",
    "permitir_multiplas_classificacoes": true,
    "max_sugestoes": 3
  }'
```

## Observações

- Se a configuração OpenAI/Azure não for informada corretamente ou a chamada falhar, o sistema usa fallback determinístico.
- As consultas externas (IBGE/NFS-e) ficam desabilitadas por padrão para evitar latência; habilite com `ENABLE_EXTERNAL_LOOKUPS=true`.
- O carregamento CATMAS tenta primeiro o Google Sheets; em caso de indisponibilidade, usa o CSV local `Retrato do Catmas - Fevereiro25 - v3.xlsx - Geral.csv`.
- Quando habilitado, o sistema gera/atualiza embeddings da base CATMAS e persiste em SQLite para busca vetorial.
- No Azure App Service, prefira armazenar o SQLite em `/home/data/catmas_vectors.db` (ou caminho definido em `CATMAS_VECTOR_DB_PATH`) para evitar filesystem temporário/somente leitura.
- Para evitar cold start alto, mantenha `ENABLE_CATMAS_VECTOR_SYNC_ON_STARTUP=false` e rode uma sincronização controlada (job/manual) quando precisar atualizar a base vetorial.
- Para produção, recomenda-se incluir camada de autenticação, trilha de auditoria e validações jurídicas adicionais.

## Deploy no Azure App Service (API)

1. Configure o Startup Command com Uvicorn/Gunicorn, por exemplo:

```bash
gunicorn -k uvicorn.workers.UvicornWorker app.main:app
```

2. Defina variáveis de ambiente no App Service:
   - `OPENAI_API_KEY`
   - `OPENAI_CHAT_MODEL=gpt-4.1-mini`
   - `OPENAI_EMBEDDING_MODEL=text-embedding-3-large`
   - `ENABLE_CATMAS_VECTOR_SEARCH=true`
   - `ENABLE_CATMAS_VECTOR_SYNC_ON_STARTUP=false`
   - `CATMAS_VECTOR_DB_PATH=/home/data/catmas_vectors.db`

3. Garanta permissao de escrita no caminho configurado para o SQLite.

## Frontend (React + Vite)

1. Acesse a pasta `frontend`.
2. Crie `.env` a partir de `frontend/.env.example` e ajuste:
   - `VITE_API_BASE_URL`
3. Instale dependências e execute:

```bash
cd frontend
npm install
npm run dev
```

## GitHub + Vercel

- Publique o repositório no GitHub.
- Na Vercel, importe o repositório e configure o **Root Directory** como `frontend`.
- Adicione a variável de ambiente `VITE_API_BASE_URL` no painel da Vercel.
- Gere o deploy e valide conectividade com a API no indicador de status da tela inicial.

## Ingestao Vetorial no Azure AI Search (RAG)

Script pronto em `scripts/ingest_catmas_to_azure_search.py` para:

1. Ler CATMAS via Google Sheets (CSV export).
2. Gerar embeddings com Azure OpenAI (`text-embedding-3-large` ou deployment superior).
3. Criar indice vetorial no Azure AI Search (se nao existir).
4. Publicar documentos vetorizados por lote.

Variaveis obrigatorias para o script:

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`
- `AZURE_SEARCH_ENDPOINT`
- `AZURE_SEARCH_API_KEY`
- `AZURE_SEARCH_INDEX_NAME` (opcional, default `catmas-index`)

Execucao:

```bash
python scripts/ingest_catmas_to_azure_search.py
```

## OCR de documentos e inferencia do objeto da contratacao

Endpoint adicional implementado:

- `POST /analisar-com-arquivos` (multipart/form-data)

Campos suportados:

- `finalidade`
- `objeto_contratacao` (pode ser vazio; sistema tenta inferir pelos documentos)
- `texto_documentos` (opcional)
- `cnpj` (opcional)
- `cnae_empresa` (opcional)
- `permitir_multiplas_classificacoes`
- `max_sugestoes`
- `arquivos` (multiplos: CI, ETP, TR, Contrato, Nota Fiscal etc.)

OCR com IA:

- Modelo padrao: `mistral-document-ai-2512`
- Variaveis necessarias:
   - `MISTRAL_API_KEY`
   - `MISTRAL_DOCUMENT_MODEL` (default `mistral-document-ai-2512`)
   - `MISTRAL_OCR_ENDPOINT` (default `https://api.mistral.ai/v1/ocr`)

Comportamento:

- O texto extraido por OCR e concatenado em `texto_documentos` para enriquecer a analise.
- O sistema tenta inferir o objeto da contratacao com base nos documentos quando o campo vier vazio.

## System Message (Azure OpenAI)

- Arquivo: `app/system_message.py`
- Funcao: `build_tjmg_system_message()`

Esse system message instrui o modelo a atuar como especialista de orcamento publico de Minas Gerais, exigindo:

- Cruzamento Finalidade x Objeto x CATMAS x Tabelas 3/4/5/7/8.
- Priorizacao de item CATMAS ATIVO.
- Proibicao de inventar codigos.
- Sinalizacao de risco tributario/CNAE.
- Saida em JSON auditavel.

## Validacao CNAE e Tributacao

- Arquivo: `app/external_integrations.py`
- Funcao: `validar_cnae_e_tributacao(objeto_contratacao, cnae_empresa)`

Retorno consolidado:

- Lista de CNAEs sugeridos pelo IBGE.
- Lista de codigos de tributacao nacional (Portal NFS-e via integrador).
- Parecer de compatibilidade CNAE x objeto.

## Seguranca e Compliance (baseline implementado)

- HSTS habilitado por middleware (`app/security.py`).
- Trilhas de auditoria com Quem, Quando, Onde e O Que por requisicao (`AuditLogMiddleware`).
- Mascara de CPF em logs por `mask_sensitive_data`.
- Middleware OIDC Keycloak com validacao de token Bearer (`app/auth.py`) ativavel por `ENABLE_AUTH=true`.

Para producao TJMG, recomenda-se complementar com:

- Integracao OIDC Keycloak para autenticacao/autorizacao de usuarios.
- WAF, varredura de vulnerabilidades e SAST/DAST no pipeline.
- Retencao de logs em Log Analytics por no minimo 6 meses.

Exemplo de variaveis para OIDC:

- `ENABLE_AUTH=true`
- `OIDC_ISSUER_URL=https://<keycloak-host>/realms/<realm>`
- `OIDC_CLIENT_ID=<client-id>`
- `OIDC_AUDIENCE=<client-id-ou-audience>`
