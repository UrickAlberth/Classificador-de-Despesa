# Relatorio Base para Criacao do Sistema

- Sistema: Classificador de Despesas (CIAR x GEFIN)
- Data: 19/03/2026
- Objetivo deste documento: consolidar todas as informacoes necessarias para construir, evoluir e colocar o sistema em producao com rastreabilidade tecnica e funcional.

## 1. Visao do Produto

O sistema deve classificar despesas publicas com base em descricao textual (finalidade, objeto e documentos), cruzando CATMAS e tabelas orcamentarias oficiais, com apoio de IA e regras de negocio explicitas.

Resultados esperados:
- sugestao de classificacao economica confiavel;
- suporte a validacao tributaria/CNAE;
- trilha de justificativa auditavel;
- operacao em dois contextos: pre-contratacao (sem CNPJ) e pos-contratacao (com CNPJ/CNAE).

## 2. Objetivos de Negocio e Sucesso

Objetivos:
1. Reduzir erro de enquadramento por Elemento/Item.
2. Diminuir tempo de analise funcional.
3. Aumentar padronizacao e auditabilidade das decisoes.

Indicadores de sucesso (KPIs):
1. Precisao Top-1 da Tabela 8 acima de meta acordada (definir baseline em homologacao).
2. Taxa de casos com validacao humana obrigatoria em queda por sprint.
3. Tempo medio por analise menor que processo manual atual.
4. Taxa de retorno com campos obrigatorios completos maior que 99%.

## 3. Escopo

### 3.1 Escopo imediato (curto prazo)

1. Foco principal em Tabela 8 (Elemento/Item) + CATMAS.
2. Leitura de documentos por item (nao apenas objeto geral).
3. Correcao da camada tributaria (retorno de CNAE/codigo tributario quando disponivel).
4. Persistencia de dados na interface para edicao e reprocessamento sem perda.

### 3.2 Escopo posterior (medio prazo)

1. Fluxo operacional completo ponta a ponta documentado e validado.
2. Incorporacao de regras MCASP no motor de decisao.
3. Melhor inferencia de CNAE sem CNPJ.
4. Expansao gradual para demais tabelas e regras complementares.

## 4. Stakeholders e Responsabilidades

1. GEFIN (funcional)
- definir e versionar regras de negocio;
- validar exemplos reais e criterios de aceite;
- aprovar fluxo operacional.

2. CIAR/Desenvolvimento (tecnico)
- implementar backend, frontend, integracoes e qualidade;
- operar logs, seguranca, testes e deploy;
- apoiar homologacao tecnica e estabilizacao.

3. Usuario final (analista)
- revisar sugestoes;
- editar dados e reprocessar;
- registrar feedback de acerto/erro para melhoria continua.

## 5. Requisitos Funcionais

### RF-01 Entrada de analise
- Receber finalidade e objeto da contratacao como entradas centrais.
- Permitir texto documental complementar.
- Permitir CNPJ e CNAE (opcional).
- Permitir multiplas sugestoes (max 1 a 10).

### RF-02 Analise com anexos
- Receber arquivos (PDF/imagens/texto/html) para OCR.
- Extrair texto e inferir objeto quando nao informado.
- Consolidar metadados de OCR no contexto de analise.

### RF-03 Classificacao economica
- Cruzar finalidade + objeto + tabelas orcamentarias + CATMAS.
- Priorizar itens CATMAS ATIVO.
- Retornar justificativa tecnica por sugestao.

### RF-04 Classificacao por item em documentos
- Identificar itens distintos no mesmo documento.
- Produzir classificacao individual por item.
- Exibir evidencias que ligam texto do item a classificacao.

### RF-05 Validacao tributaria e CNAE
- Consultar CNAE sugerido por servico externo (IBGE).
- Consultar codigo de tributacao nacional quando integracao estiver disponivel.
- Funcionar com e sem CNPJ/CNAE informado.

### RF-06 Alertas e confianca
- Retornar alertas de inconsistencias (CNAE, CATMAS inativo/suspenso, ambiguidade).
- Indicar quando validacao humana e obrigatoria.

### RF-07 Usabilidade e estado
- Preservar dados da tela entre analises.
- Permitir edicao incremental e reprocessamento.
- Manter historico de execucao da sessao (recomendado).

### RF-08 Rastreabilidade
- Informar fontes consultadas.
- Informar regras aplicadas e justificativas.
- Informar nivel de similaridade e candidatos alternativos.

## 6. Regras de Negocio (Minimo Necessario)

### RN-01 Prioridade de classificacao
- Nesta fase, priorizar Tabela 8 para decisao principal.
- Demais tabelas podem ser auxiliares para coerencia.

### RN-02 CATMAS
- Nunca inventar codigo.
- Aceitar apenas codigo existente em base oficial.
- Priorizar itens com status ATIVO.

### RN-03 Ambiguidade
- Quando houver proximidade entre candidatos, marcar validacao humana.
- Exibir itens semelhantes com grau de similaridade.

### RN-04 Tributario
- Se API externa falhar, retornar fallback explicito sem quebrar analise.
- Diferenciar cenario sem CNPJ (inferencia) e com CNPJ/CNAE (validacao).

### RN-05 Conformidade
- Manter alinhamento normativo minimo (Lei 14.133/2021 e Res. CNJ 370/2021).
- Incluir MCASP como base de regra para casos complexos (fase seguinte).

## 7. Fontes de Dados e Conhecimento

Fontes atuais:
1. CATMAS/SIAD (Google Sheets, com fallback CSV local).
2. Classificador economico de despesas MG.
3. Tabelas orcamentarias 3, 4, 5, 7 e 8.
4. Documentos administrativos do processo SEI usado como contexto.
5. API IBGE para CNAE.
6. API NFS-e (quando configurada) para tributacao nacional.

Requisitos de dados:
1. Atualizacao periodica da base CATMAS.
2. Controle de versao das tabelas e regras.
3. Registro de data e origem da ultima sincronizacao.
4. Dicionario de dados funcional para cada coluna critica.

## 8. Contratos de API (Estado Atual)

### 8.1 Endpoints
1. GET /health
2. GET /
3. POST /analisar
4. POST /analisar-com-arquivos

### 8.2 Entrada principal de analise
Campos:
1. finalidade (obrigatorio, minimo 10)
2. objeto_contratacao (obrigatorio, minimo 10 no endpoint JSON)
3. texto_documentos (opcional)
4. cnpj (opcional)
5. cnae_empresa (opcional)
6. permitir_multiplas_classificacoes (bool)
7. max_sugestoes (1 a 10)

### 8.3 Saida principal
1. sugestoes[] com campos completos de classificacao
2. cruzamento_obrigatorio_realizado
3. compatibilidade_cnae
4. alertas[]
5. observacoes_tecnicas[]
6. alinhamento_normativo[]
7. fontes_consultadas[]

## 9. Arquitetura de Solucao

### 9.1 Backend
- Stack: FastAPI + Pydantic.
- Camadas principais:
1. API e validacao de entrada.
2. Servico de orquestracao de classificacao.
3. Repositorio de dados e ranking.
4. Cliente de IA para sugestoes.
5. Integracoes externas (CNAE/tributacao).
6. Seguranca, autenticacao e auditoria.

### 9.2 IA e busca
- Uso de modelo de linguagem para consolidar sugestoes.
- Busca textual e opcional busca vetorial CATMAS (embeddings + SQLite).
- Fallback deterministico quando IA retorna estrutura parcial.

### 9.3 Frontend
- Stack: React + Vite + TypeScript.
- Funcoes:
1. formulario de entrada;
2. upload de anexos;
3. acompanhamento por etapas;
4. exibicao de resultado e alertas;
5. capacidade de edicao/reanalise (a reforcar).

## 10. Seguranca, Compliance e Auditoria

Controles ja previstos:
1. HSTS por middleware.
2. Auditoria por requisicao com quem/quando/onde/o_que.
3. Mascara de dados sensiveis (CPF) em logs.
4. OIDC opcional com Keycloak e validacao JWT.

Controles obrigatorios para producao:
1. OIDC habilitado em ambiente produtivo.
2. Gestao de segredo por cofre seguro.
3. WAF e hardening de rede.
4. SAST/DAST no pipeline.
5. Politica de retencao de logs (ex.: minimo 6 meses).
6. Politica de LGPD para dados pessoais em anexos/documentos.

## 11. Requisitos Nao Funcionais

### RNF-01 Desempenho
- Tempo de resposta alvo por analise: definir SLA por ambiente.
- Suporte a anexos de tamanho controlado com timeout previsivel.

### RNF-02 Disponibilidade
- Definir SLO de disponibilidade para API e integrações externas.
- Fallback quando servicos externos indisponiveis.

### RNF-03 Confiabilidade
- Idempotencia de chamadas quando aplicavel.
- Tratamento robusto de erro com mensagens acionaveis.

### RNF-04 Observabilidade
- Logs estruturados.
- Correlacao por request id.
- Metricas de acuracia, latencia e falha por componente.

### RNF-05 Manutenibilidade
- Regras de negocio versionadas.
- Testes automatizados por camada.
- Documentacao tecnica e funcional sincronizada.

## 12. Lacunas Criticas a Resolver

1. Segmentacao item a item de PDF/TR ainda precisa robustez funcional.
2. Persistencia de estado no frontend para evitar perda ao reprocessar.
3. Dependencia de API tributaria publica sem garantia de disponibilidade.
4. Definicao formal das regras MCASP para motor de decisao.
5. Definicao de baseline de qualidade para homologacao (precisao e cobertura).

## 13. Plano de Implementacao por Fase

### Fase 1 - Estabilizacao do MVP
1. Ajustar foco tecnico para Tabela 8 + CATMAS.
2. Implementar extração e classificacao por item.
3. Corrigir e robustecer camada tributaria com fallback.
4. Persistir estado da interface para edicao incremental.

### Fase 2 - Confiabilidade e regras
1. Incorporar MCASP em regras explicitas.
2. Melhorar inferencia CNAE sem CNPJ.
3. Refinar explicabilidade da decisao (regra aplicada + evidencia).

### Fase 3 - Pronto para producao
1. Endurecer seguranca e governanca de dados.
2. Fechar monitoramento/alertas operacionais.
3. Executar homologacao funcional e tecnica final.
4. Publicar processo de suporte e operacao.

## 14. Estrategia de Testes

### 14.1 Testes funcionais
1. Casos simples (1 item, descricao clara).
2. Casos ambiguos (itens semelhantes).
3. Documentos com multiplos itens.
4. Cenario sem CNPJ e com CNPJ/CNAE.
5. Cenario de falha de API externa.

### 14.2 Testes tecnicos
1. Unitarios para regras de classificacao.
2. Integracao para endpoints e integrações.
3. Contrato para schema de resposta.
4. Carga e resiliencia para OCR e IA.

### 14.3 Criterios de aceite minimos
1. Nao haver codigo inventado na saida.
2. Sempre haver justificativa e fontes consultadas.
3. Alertas coerentes para ambiguidade e incompatibilidades.
4. Fluxo de edicao/reanalise sem perda de dados.

## 15. Infraestrutura e Deploy

Ambiente alvo sugerido:
1. Backend em Azure App Service (FastAPI com Uvicorn/Gunicorn).
2. Frontend em Vercel (Vite).
3. Persistencia vetorial local SQLite em caminho persistente do ambiente.
4. Opcional: Azure AI Search para RAG vetorial em escala.

Variaveis de ambiente essenciais:
1. Provedor IA e credenciais (OpenAI ou Azure OpenAI).
2. Chaves de OCR (Mistral), quando habilitado.
3. Endpoints/chaves de busca tributaria e CNAE.
4. Flags de busca vetorial e sincronizacao.
5. Configuracoes OIDC para autenticacao.

## 16. Governanca de Regras e Dados

1. Cada regra de classificacao deve ter dono funcional, versao e data de vigencia.
2. Mudancas de regra devem passar por homologacao controlada.
3. Base CATMAS/tabelas deve ter trilha de atualizacao e rollback.
4. Catalogo de exemplos de treinamento e validacao deve ser mantido.

## 17. Checklist de Kickoff (O que precisa estar definido)

### Funcional (GEFIN)
1. Lista de casos reais priorizados para homologacao.
2. Criterio objetivo de acerto por tipo de item.
3. Regras MCASP priorizadas por impacto.
4. Fluxo operacional desejado ponta a ponta.

### Tecnico (CIAR/Dev)
1. Ambientes (dev/homolog/prod) provisionados.
2. Segredos e variaveis de ambiente definidos.
3. Pipeline CI/CD com testes e seguranca.
4. Plano de monitoramento e suporte.

### Integracoes
1. Confirmacao de disponibilidade e limites de APIs externas.
2. Definicao de fallback para indisponibilidade.
3. Politica de timeout, retentativa e cache.

## 18. Entregaveis Recomendados

1. Documento de regras de negocio versionado.
2. Matriz de rastreabilidade requisito -> teste -> evidencia.
3. Suite de testes automatizados por camada.
4. Painel de metricas operacionais e de qualidade.
5. Guia operacional para usuarios e suporte.

## 19. Conclusao

A base atual comprova viabilidade tecnica, mas a passagem para um sistema confiavel depende de quatro frentes sincronizadas:
1. granularidade por item (documentos e classificacao);
2. regras explicitas e versionadas (incluindo MCASP);
3. robustez de integrações com fallback;
4. experiencia de uso com persistencia e rastreabilidade.

Com este conjunto fechado, o sistema passa de prototipo para produto operacional com governanca e capacidade de evolucao continua.
