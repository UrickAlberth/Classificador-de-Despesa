# Frontend - Classificador de Despesa

Frontend em React + Vite para operar o fluxo completo do MVP, com:

- formulário de entrada da análise;
- painel de andamento por etapas;
- exibição estruturada do resultado retornado pela API FastAPI;
- configuração por variáveis de ambiente para deploy na Vercel.

## Requisitos

- Node.js 20+
- API backend em execução (local ou publicada)

## Variáveis de ambiente

Copie `.env.example` para `.env` e ajuste:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Em produção, use a URL pública da API.

## Execução local

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
npm run preview
```

## Deploy na Vercel

1. Suba o repositório no GitHub.
2. Na Vercel, importe o repositório.
3. Defina **Root Directory** como `frontend`.
4. Configure a variável de ambiente `VITE_API_BASE_URL` com a URL da sua API.
5. Faça o deploy.

> Observação: por segurança, nunca commite `.env` no repositório.