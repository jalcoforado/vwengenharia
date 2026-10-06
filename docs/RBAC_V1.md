# Matriz de Permissoes - VW Engenharia ERP V1

## Principio

A autorizacao e aplicada no backend. A interface pode esconder acoes nao permitidas, mas nunca substitui RBAC no servidor.

Todo acesso operacional e limitado pelo tenant da membership autenticada.

## Perfis

### SUPERADMIN
Pode:
- administrar cadastros mestres;
- administrar equipe;
- configurar checklists e planos;
- operar gestao de visitas;
- revisar visitas;
- administrar ocorrencias, OS e manutencoes;
- consultar auditoria;
- gerar e revogar chaves de integracao;
- executar migracao historica;
- consultar dashboards, relatorios e exportacoes.

Uso:
- administracao tecnica/funcional excepcional.

### ADMIN
Pode:
- tudo que o GESTOR pode;
- administrar equipe;
- gerar/revogar chaves de integracao;
- executar migracao historica;
- administrar configuracoes operacionais.

Uso:
- administrador principal da VW Engenharia.

### GESTOR
Pode:
- consultar e operar cadastros de negocio;
- planejar visitas;
- revisar visitas;
- criar e acompanhar OS;
- validar OS;
- acompanhar manutencoes;
- tratar solicitacoes de materiais/servicos;
- consultar dashboards, alertas, relatorios e auditoria.

Nao pode:
- administrar chaves de integracao;
- executar migracao historica;
- assumir privilegios de SUPERADMIN.

### SUPERVISOR
Pode:
- acompanhar operacao;
- revisar visitas;
- planejar/acompanhar agenda;
- criar/atribuir/acompanhar OS dentro das permissoes do backend;
- acompanhar manutencoes e solicitacoes;
- consultar indicadores operacionais.

Nao pode:
- consultar auditoria administrativa;
- administrar integracoes;
- executar migracao historica;
- administrar usuarios de nivel superior.

### TECNICO
Pode:
- consultar sua propria agenda operacional;
- iniciar/finalizar visitas atribuidas;
- preencher checklist;
- registrar medicoes;
- anexar evidencias;
- registrar ocorrencias;
- solicitar material/servico/terceiro a partir da operacao permitida;
- consultar suas proprias pendencias;
- operar offline e sincronizar.

Nao pode:
- consultar visitas de outro tecnico fora do escopo permitido;
- validar OS;
- consultar auditoria;
- criar chaves de integracao;
- executar migracao;
- criar cadastros mestres;
- administrar equipe.

### MANUTENCAO
Pode:
- consultar atividades e OS atribuidas;
- executar manutencoes;
- registrar execucao preventiva/corretiva;
- concluir OS conforme maquina de estados;
- consultar sua propria fila operacional.

Nao pode:
- validar OS;
- consultar auditoria administrativa;
- administrar integracoes;
- executar migracao;
- criar cadastros mestres.

### CLIENTE
A V1 mantem o perfil reservado para evolucao de portal do cliente.

Antes de liberar qualquer endpoint ao perfil CLIENTE:
- definir explicitamente quais estacoes/empreendimentos o usuario cliente pode consultar;
- aplicar escopo por relacao de negocio, alem de tenant;
- impedir acesso a dados internos de equipe, auditoria e configuracao.

Por seguranca, nenhuma permissao ampla deve ser inferida apenas pela existencia desse papel.

## Matriz resumida

| Capacidade | Superadmin | Admin | Gestor | Supervisor | Tecnico | Manutencao | Cliente |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Cadastros mestres | Sim | Sim | Sim | Conforme API | Nao | Nao | Nao |
| Equipe | Sim | Sim | Nao | Nao | Nao | Nao | Nao |
| Planejamento de visitas | Sim | Sim | Sim | Sim | Nao | Nao | Nao |
| Executar visita | Nao usual | Nao usual | Nao usual | Nao usual | Sim | Conforme atribuicao | Nao |
| Criar ocorrencia | Sim | Sim | Sim | Sim | Sim | Conforme contexto | Nao |
| Criar/gerir OS | Sim | Sim | Sim | Sim | Limitado | Limitado | Nao |
| Validar OS | Sim | Sim | Sim | Conforme regra backend | Nao | Nao | Nao |
| Executar manutencao | Sim | Sim | Sim | Sim | Conforme atribuicao | Sim | Nao |
| Revisar visita | Sim | Sim | Sim | Sim | Nao | Nao | Nao |
| Materiais/servicos | Sim | Sim | Sim | Sim | Solicitar | Solicitar/acompanhar | Nao |
| Dashboard | Sim | Sim | Sim | Sim | Minha fila | Minha fila | Futuro |
| Auditoria | Sim | Sim | Sim | Nao | Nao | Nao | Nao |
| Integracao iAnalisys | Sim | Sim | Nao | Nao | Nao | Nao | Nao |
| Migracao historica | Sim | Sim | Nao | Nao | Nao | Nao | Nao |

## Regras que nao podem ser quebradas

1. Tenant e sempre determinado pela sessao/credencial, nunca por parametro livre do cliente.
2. Objetos de outro tenant devem parecer inexistentes quando apropriado.
3. Tecnico nao pode ampliar o proprio escopo alterando IDs na requisicao.
4. Atribuicao nao concede privilegio de validacao.
5. Integracao iAnalisys e somente leitura na V1.
6. Migracao historica e exclusiva de ADMIN/SUPERADMIN.
7. Auditoria nao pode ser apagada pela interface operacional.
8. Inativacao e preferida a exclusao para entidades com historico.
