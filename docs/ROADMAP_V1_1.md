# Roadmap V1.1 - Endurecimento Operacional

## Objetivo

Levar o ERP da VW Engenharia da V1 funcional para uma versao de homologacao e operacao real mais robusta, mantendo a fronteira arquitetural definida:

- VW Engenharia ERP = operacao transacional;
- iAnalisys = BI, analise e IA;
- nenhuma dependencia de LLM dentro do ERP.

## Prioridade P0 - Homologacao real

1. Criar relatorio imprimivel/PDF de visita concluida, com:
   - cliente, empreendimento e estacao;
   - tecnico e horarios;
   - checklist;
   - medicoes;
   - ocorrencias;
   - fotos/evidencias;
   - assinatura/validacao da gestao quando aplicavel.

2. Melhorar agenda operacional:
   - calendario mensal/semanal;
   - filtros por tecnico, cliente, empreendimento e estacao;
   - destaque visual para atraso, hoje e proximas visitas;
   - reagendamento com motivo e auditoria.

3. Fortalecer experiencia mobile:
   - compressao de fotos antes do upload;
   - indicador explicito de sincronizacao;
   - tentativa de reenvio;
   - tela de conflitos/erros da outbox;
   - bloqueio de perda acidental de rascunho.

4. Criar fluxo de aceite da homologacao:
   - roteiro por perfil;
   - evidencias do teste;
   - checklist de aceite;
   - registro de defeitos encontrados.

## Prioridade P1 - Operacao de campo

5. QR Code por estacao e ativo:
   - abrir diretamente a ficha correta;
   - iniciar visita a partir da estacao;
   - consultar historico do ativo.

6. Painel de pendencias operacionais:
   - ocorrencias sem OS;
   - OS vencendo;
   - OS fora do SLA;
   - visitas atrasadas;
   - solicitacoes aguardando atendimento;
   - preventivas proximas do vencimento.

7. Melhorar comunicacao operacional sem virar chat:
   - comentarios de acompanhamento em ocorrencia/OS;
   - mencao simples de responsavel;
   - trilha cronologica unica;
   - sem IA generativa.

## Prioridade P1 - Cliente

8. Consolidar o perfil CLIENTE:
   - acesso somente aos seus empreendimentos;
   - visitas realizadas;
   - ocorrencias e OS relacionadas;
   - evidencias liberadas;
   - relatorios de visita;
   - sem acesso a dados internos de outros clientes.

## Prioridade P2 - Operacao segura

9. Backup e recuperacao:
   - rotina documentada;
   - teste de restore;
   - politica de retencao;
   - object storage incluido no plano de recuperacao.

10. Observabilidade:
   - healthcheck consolidado;
   - logs estruturados;
   - metricas basicas de API;
   - erros de sincronizacao;
   - uso de storage;
   - alertas operacionais.

11. Importacao historica:
   - executar carga de amostra real;
   - reconciliar totais;
   - registrar divergencias;
   - emitir relatorio de migracao.

## Criterio de saida da V1.1

A V1.1 sera considerada pronta quando:

- a jornada de homologacao for executada por ADMIN, TECNICO e MANUTENCAO;
- o PWA funcionar offline e sincronizar sem duplicidade;
- relatorio de visita puder ser entregue ao cliente;
- QR Code funcionar para estacao/ativo;
- o perfil CLIENTE estiver isolado por tenant/cliente;
- backup e restore estiverem documentados e testados;
- CI permanecer verde;
- nenhum recurso de BI/IA for incorporado ao ERP.
