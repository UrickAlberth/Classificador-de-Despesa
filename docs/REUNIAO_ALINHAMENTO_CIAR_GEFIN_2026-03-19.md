# Reuniao de Alinhamento CIAR x GEFIN

- Tema: Prototipo - Classificador de Despesas
- Data: 19/03/2026
- Duracao: ~29 min
- Objetivo: avaliar o prototipo, consolidar feedback funcional e definir ajustes de curto/medio prazo.

## Resultado Geral

- O prototipo foi bem recebido como base inicial e prova de viabilidade.
- O desempenho atual de classificacao ainda nao atende o nivel de confianca esperado.
- A evolucao deve seguir ciclo iterativo, com foco em ganho de precisao por incrementos.

## Decisoes da Reuniao

1. Priorizar inicialmente a classificacao por Elemento/Item (Tabela 8).
2. Adiar evolucao das demais tabelas (categoria, modalidade etc.) para fases posteriores.
3. Tratar documentos com extracao e classificacao item a item.
4. Ajustar a integracao tributaria para cobrir dois cenarios operacionais:
   - pre-contratacao: sem CNPJ, com inferencia por IA;
   - pos-contratacao: com CNPJ/CNAE informado.
5. Preservar dados na interface para permitir edicao incremental e reprocessamento.

## Principais Problemas Identificados

### 1) Classificacao economica (Elemento/Item)

- Dificuldade na identificacao correta da classificacao.
- Excesso de tabelas no fluxo inicial, elevando ambiguidade.
- Baixa precisao no cruzamento com CATMAS para itens semelhantes.
- Ponto critico: diferenciar descricoes parecidas (ex.: tipos de lixeira).

### 2) Uso das tabelas

- Recomendacao de escopo: concentrar apenas na Tabela 8 nesta fase.
- Melhoria chave: usar o campo de interpretacao da Tabela 8 para enriquecer decisao.

### 3) Leitura de documentos (PDF/TR)

- Limitacao atual para documentos com multiplos itens.
- O sistema precisa extrair e classificar cada item separadamente.

### 4) Integracao com CATMAS

- Codigo de material em nivel generico.
- Diferenciacao real ocorre no nivel da descricao detalhada do item.
- Classificacao depende de descricao especifica, tipo (consumo x permanente) e natureza da despesa.

### 5) Classificacao tributaria

- Falhas observadas em testes: codigo tributario ausente e CNAE nao identificado.
- Hipotese principal: instabilidade/limitacao na API publica atual.

### 6) Usabilidade

- Reanalise limpa dados previamente preenchidos.
- Necessidade de manter estado para ajustes incrementais sem retrabalho.

## Nova Fonte de Regras

- Incluir MCASP (Manual de Contabilidade Aplicada ao Setor Publico) como base de apoio decisorio.
- Usar MCASP principalmente em decisoes complexas, como grupo de despesa.

## Backlog Priorizado

## Curto Prazo (Sprint imediata)

1. Foco funcional em Tabela 8 + CATMAS
   - Resultado esperado: classificacao primaria orientada a Elemento/Item.
   - Criterio de aceite: respostas retornam justificativa baseada em descricao/interpretacao da Tabela 8.

2. Extracao e classificacao por item em documentos
   - Resultado esperado: cada item identificado em PDF/TR gera uma classificacao dedicada.
   - Criterio de aceite: documento com N itens retorna N blocos de classificacao.

3. Correcao da integracao tributaria
   - Resultado esperado: retorno consistente de codigo tributario e CNAE quando houver dados validos.
   - Criterio de aceite: testes com e sem CNPJ concluem sem campos tributarios vazios indevidos.

4. Persistencia de dados na interface
   - Resultado esperado: usuario pode editar e reprocessar sem perder entradas anteriores.
   - Criterio de aceite: ciclo editar -> reanalisar preserva dados e historico da sessao.

## Medio Prazo

1. Definicao e documentacao do fluxo operacional ponta a ponta.
2. Incorporacao explicita das regras MCASP no motor de decisao.
3. Melhoria de inferencia de CNAE em contexto sem CNPJ.

## Responsabilidades

- Equipe funcional (GEFIN): detalhamento e validacao das regras de negocio e fluxo completo.
- Equipe tecnica (CIAR/dev): implementacao, testes tecnicos e evolucao da arquitetura.

## Riscos e Mitigacoes

1. Risco: ambiguidade semantica em descricoes curtas de itens.
   - Mitigacao: exigir campo de descricao detalhada + heuristicas de normalizacao.

2. Risco: dependencia de API publica para tributacao/CNAE.
   - Mitigacao: fallback por inferencia local e registro de indisponibilidade externa.

3. Risco: baixa rastreabilidade da decisao automatica.
   - Mitigacao: resposta com trilha de justificativa (fontes, regra aplicada, confianca).

## Proximos Passos

1. Implementar ajustes de curto prazo.
2. Executar nova rodada de testes funcionais com GEFIN.
3. Realizar reuniao de validacao apos correcao dos itens criticos.
4. Avaliar transicao para equipe de desenvolvimento focada em producao.

## Conclusao Tecnica

O prototipo comprova a viabilidade da solucao, mas ainda esta em fase inicial.
O principal desafio e converter interpretacao textual de documentos em classificacao estruturada confiavel, com:

- modelagem de dados mais granular por item;
- regras de negocio explicitas e versionadas;
- maior robustez em integracoes externas e explicabilidade da resposta.
