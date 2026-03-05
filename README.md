# Sistema IA de Classificação de Despesa (TJMG) - MVP

MVP em Python com FastAPI para classificação econômica da despesa e apoio tributário, usando:

- Base local CATMAS/SIAD (CSV);
- Tabelas orçamentárias (XLSX) com foco em Tabelas 3, 4, 5, 7 e 8;
- Documentos do processo SEI 0038700-03.2026.8.13.0000 como contexto de conhecimento;
- Integração de IA com Gemini 2.5 via chave de API.

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
- `app/gemini_client.py`: integração Gemini 2.5.
- `app/service.py`: orquestração e regras de negócio.
- `frontend/`: aplicação React para operação do fluxo com painel de andamento.

## Como executar

1. Crie `.env` a partir de `.env.example` e preencha:
   - `GEMINI_API_KEY`
   - `ENABLE_EXTERNAL_LOOKUPS=true` (para habilitar consultas online)
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

- Se a chave Gemini não for informada ou a chamada falhar, o sistema usa fallback determinístico.
- As consultas externas (IBGE/NFS-e) ficam desabilitadas por padrão para evitar latência; habilite com `ENABLE_EXTERNAL_LOOKUPS=true`.
- Para produção, recomenda-se incluir camada de autenticação, trilha de auditoria e validações jurídicas adicionais.

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
