# MW Engenharia ERP - Release Readiness V1

## Status alvo

A V1 e considerada pronta para homologacao quando todos os itens obrigatorios abaixo estiverem verdes no mesmo commit do `main`.

## 1. Escopo funcional obrigatorio

### Cadastros
- [x] Clientes
- [x] Empreendimentos
- [x] Estacoes
- [x] Tipos de ativo
- [x] Ativos
- [x] Inativacao e reativacao sem apagar historico
- [x] Visao 360 por estacao

### Equipe e acesso
- [x] Tenant
- [x] Usuarios
- [x] Perfis RBAC
- [x] Equipe de campo/manutencao
- [x] Troca de senha
- [x] Refresh token e revogacao

### Planejamento
- [x] Plano recorrente de visita
- [x] Geracao idempotente da agenda
- [x] Pausar plano
- [x] Checklist configuravel e versionado
- [x] Campos obrigatorios

### Operacao de campo
- [x] PWA
- [x] Offline/outbox
- [x] Iniciar e finalizar visita
- [x] Checklist dinamico
- [x] Medicoes estruturadas
- [x] Evidencias
- [x] Ocorrencias
- [x] Solicitacao de material/servico/terceiro
- [x] Idempotencia de comandos

### Ordens de servico
- [x] OS avulsa ou originada de ocorrencia
- [x] Responsavel
- [x] Prioridade e SLA
- [x] Maquina de estados
- [x] Historico de estados
- [x] Execucao pela manutencao
- [x] Conclusao
- [x] Validacao pela gestao

### Manutencao
- [x] Plano preventivo por ativo
- [x] Periodicidade
- [x] Responsavel
- [x] Proximo vencimento
- [x] Registro de execucao
- [x] Recalculo da proxima preventiva
- [x] Manutencao corretiva vinculavel a OS

### Gestao
- [x] Minha Fila por perfil
- [x] Alertas operacionais
- [x] Dashboard operacional
- [x] Fila de revisao
- [x] Materiais/servicos
- [x] Exportacao CSV
- [x] Auditoria consultavel
- [x] Navegacao por Visao Geral / Operacao / Cadastros / Configuracao / Governanca

### Integracao iAnalisys
- [x] Chaves read-only por tenant
- [x] Segredo exibido uma unica vez
- [x] Revogacao de chave
- [x] Recursos de leitura versionados em /integration/v1
- [x] Watermark incremental
- [x] Isolamento de tenant
- [x] ERP sem dependencia de LLM

### Migracao historica
- [x] Upload XLSX
- [x] Staging bruto
- [x] Fingerprint idempotente
- [x] Linha e arquivo de origem
- [x] Mapeamento historico de estacoes
- [x] Mapeamento historico de tecnicos
- [x] Auto-mapeamento apenas para correspondencia exata sem colisao
- [x] Mapeamento manual
- [x] Materializacao em lotes
- [x] Status historico preservado no staging
- [x] Historico nao vira backlog atual por padrao
- [x] Conversao America/Fortaleza -> UTC
- [x] Relatorio de erros e pendencias

## 2. Invariantes de seguranca

- [x] Toda entidade operacional e tenant-scoped.
- [x] Leitura de usuario de campo e limitada ao seu contexto operacional.
- [x] Tecnico nao acessa auditoria.
- [x] Tecnico nao administra integracoes.
- [x] Tecnico nao executa migracao.
- [x] Tecnico nao cria cadastros mestres.
- [x] Apenas gestao valida OS.
- [x] Credencial iAnalisys e revogavel e nao armazena segredo em texto puro.
- [x] Anexos usam object storage; banco guarda metadados.
- [x] Operacoes offline possuem identificador idempotente.

## 3. Gate automatizado de release

O GitHub Actions deve passar:

1. `ruff check app tests scripts alembic`
2. `alembic upgrade head`
3. `pytest -q`
4. `npm install`
5. `npm run build`

O teste `test_v1_complete_operational_journey` e o teste de RBAC da V1 fazem parte do gate.

## 4. Jornada minima de homologacao manual

Executar em ambiente de homologacao com navegador desktop e um telefone/tablet:

1. ADMIN cria cliente, empreendimento, estacao e ativo.
2. ADMIN cria checklist e plano semanal.
3. ADMIN gera agenda.
4. TECNICO sincroniza o PWA.
5. Desligar rede do aparelho.
6. TECNICO inicia visita, responde checklist, registra medicao, ocorrencia e solicitacao.
7. TECNICO finaliza visita ainda offline.
8. Religando a rede, confirmar sincronizacao sem duplicidade.
9. ADMIN revisa a visita.
10. ADMIN gera OS da ocorrencia e atribui MANUTENCAO.
11. MANUTENCAO inicia e conclui o servico.
12. ADMIN valida a OS.
13. ADMIN marca solicitacao como atendida.
14. Abrir Visao 360 da estacao e conferir o historico.
15. Conferir Minha Fila e Alertas.
16. Conferir Auditoria.
17. Criar chave iAnalisys, consultar recursos e revogar a chave.
18. Importar uma copia da planilha em staging e conferir contagens antes de materializar.

## 5. Dados historicos MW

Antes da carga definitiva:

- manter backup imutavel do XLSX original;
- executar staging completo;
- revisar rotulos nao mapeados;
- conferir contagem de entrada contra a fonte;
- materializar primeiro uma amostra;
- reconciliar estacoes, tecnicos, datas e quantidade de visitas;
- importar o restante em lotes;
- manter `preserve_source_review_status=false` salvo decisao expressa da MW.

A planilha historica conhecida possui aproximadamente 13,8 mil registros. A contagem definitiva de migracao deve ser obtida pelo proprio staging da versao usada na carga.

## 6. Operacao inicial recomendada

Durante a homologacao, manter o Excel apenas como referencia paralela e nao como dupla fonte de escrita.

Apos aceite:
- novo registro operacional nasce apenas no ERP;
- planilha passa a ser historico/backup;
- iAnalisys consome apenas a API de integracao;
- nenhuma escrita do iAnalisys retorna ao ERP na V1.

## 7. Fora da V1

Permanecem fora do escopo por decisao arquitetural:

- financeiro completo;
- folha/pessoal;
- compras completas;
- estoque completo;
- roteirizacao otimizada;
- BI analitico avancado;
- chat;
- agentes;
- RAG;
- LLM;
- fine-tuning;
- manutencao preditiva por IA.

Essas capacidades pertencem a outros produtos ou a fases posteriores. O iAnalisys continua sendo a camada de BI e inteligencia.
