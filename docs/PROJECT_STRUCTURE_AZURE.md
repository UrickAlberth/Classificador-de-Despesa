# Estrutura de Projeto Recomendada (Azure + IA)

## Visao Geral

- frontend/: SPA React (Vite), aderente ao Design System do TJMG.
- app/: API FastAPI com orquestracao de negocio e IA.
- scripts/: ingestao e indexacao RAG para Azure AI Search.
- docs/: arquitetura, operacao, seguranca e compliance.
- infra/: IaC para App Service, Azure AI Search, Key Vault, Monitor.

## Estrutura de Pastas

~~~text
.
|-- app/
|   |-- main.py
|   |-- service.py
|   |-- data_sources.py
|   |-- external_integrations.py
|   |-- gemini_client.py
|   |-- system_message.py
|   |-- security.py
|   |-- schemas.py
|-- api/
|   |-- index.py
|-- frontend/
|   |-- src/
|   |   |-- components/
|   |   |-- hooks/
|   |   |-- services/
|   |   `-- styles.css
|-- scripts/
|   `-- ingest_catmas_to_azure_search.py
|-- docs/
|   `-- PROJECT_STRUCTURE_AZURE.md
|-- infra/
|   |-- bicep/
|   `-- pipelines/
|-- requirements.txt
`-- README.md
~~~

## Servicos Azure Alvo

- Azure App Service (backend FastAPI)
- Azure OpenAI Service
: deployment de chat: gpt-5.2-chat
: deployment de embedding: text-embedding-3-large
- Azure AI Search
: indice vetorial CATMAS
- Azure Key Vault
: segredos de API e OIDC
- Azure Monitor + Log Analytics
: trilha de auditoria e retencao minima de 6 meses

## Diretrizes de Conformidade

- OIDC com Keycloak para autenticacao federada.
- TLS 1.3 no endpoint publico e cabecalho HSTS ativo.
- Auditoria com Quem, Quando, Onde e O Que por requisicao.
- Mascara de dados sensiveis (ex.: CPF) nos logs e respostas operacionais.
- Praticas OWASP Top 10 no SDLC e scans de dependencia no pipeline.
