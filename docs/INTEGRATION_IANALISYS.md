# Integração ERP MW Engenharia -> iAnalisys

## Objetivo

O ERP MW Engenharia é a fonte transacional. O iAnalisys consome dados operacionais por uma API somente leitura.

O iAnalisys não acessa diretamente o PostgreSQL do ERP e não reutiliza login de usuário.

## Autenticação

Um ADMIN/SUPERADMIN cria uma credencial de integração:

- POST /api/v1/integration-keys
- GET /api/v1/integration-keys
- POST /api/v1/integration-keys/{id}/revoke

O segredo completo é retornado somente na criação. O ERP armazena apenas SHA-256 e um prefixo para identificação.

Nas chamadas de integração:

```text
X-Integration-Key: mwk_<segredo>
```

O tenant é derivado da credencial. Não existe parâmetro tenant_id na API externa.

## API v1

Base:

```text
GET /api/v1/integration/v1/{resource}
```

Recursos:

- clients
- client-contacts
- contracting-parties
- developments
- stations
- process-unit-types
- process-units
- assets
- visit-plans
- visits
- visit-asset-situations
- measurements
- occurrences
- work-orders
- work-order-history
- reviews

Parâmetros:

- updated_since: watermark exclusivo da última sincronização
- snapshot_at: fixa o instante lógico durante paginação
- limit: 1 a 1000, padrão 500
- offset: padrão 0

Datas de watermark devem incluir timezone.

### contracting-parties

Quem contrata a MW (pessoa física ou jurídica): `person_type`, `name` (razão social ou nome), `trade_name`, `document` (CPF/CNPJ), `contact_email`, `contact_phone`, `is_active`. Um contratante pode ter vários empreendimentos; a ligação está em `developments.contracting_party_id`.

### process-unit-types e process-units

A estação é dividida em unidades de processo (gradeamento, reator UASB, tanque de contato...). `process-unit-types` é o catálogo (`name`, `code`, `stage`); `process-units` são as unidades instaladas (`station_id`, `unit_type_id`, `name`). O recurso `assets` traz `process_unit_id`; vazio significa equipamento na área geral da estação.

### visit-asset-situations

Uma linha por visita e equipamento: como o técnico encontrou o equipamento (`visit_id`, `asset_id`, `situation`, `comment`). Valores de `situation`: FUNCIONANDO, DESLIGADO, NECESSARIO_VERIFICAR, AGUARDANDO_RETIRADA, RETIRADO_AGUARDANDO_MANUTENCAO, EM_MANUTENCAO, AGUARDANDO_INSTALACAO, NAO_POSSUI, OUTRO. Cada registro também atualiza `assets.status`, exceto OUTRO.

### client-contacts

Uma linha por responsável, empreendimento e área de responsabilidade. Para a MW, o cliente é o empreendimento; o cadastro `clients` guarda os responsáveis, pessoas físicas ou jurídicas que respondem por um ou mais empreendimentos. Um empreendimento tem um responsável principal e pode ter outros.

Correspondência com a dimensão Cliente do iAnalisys:

| Dimensão Cliente | Campo no recurso | Origem no ERP |
| --- | --- | --- |
| id_cliente | client_id | clients.id |
| id_empreendimento | development_id | developments.id |
| escopo_contato | scope | GERAL, TECNICO, FINANCEIRO, COMERCIAL ou ADMINISTRATIVO |
| nome | name | clients.name |
| funcao | contact_role | clients.contact_role |
| telefone | contact_phone | clients.contact_phone |
| whatsapp | contact_whatsapp | clients.contact_whatsapp |
| email | contact_email | clients.contact_email |

O recurso também traz `id` (do vínculo), `is_primary`, `is_active`, `created_at` e `updated_at`.

O responsável principal de cada empreendimento aparece como uma linha com `is_primary = true` e escopo `GERAL`, e coincide com `developments.client_id`.

`updated_at` é o maior entre a alteração do vínculo e a do cliente. Assim, mudar o telefone de um cliente reenvia todas as linhas dele na carga incremental.

O recurso `developments` traz também `document` (CNPJ), `contact_phone` e `contact_email` do empreendimento.

A liberação de portal por empreendimento não é exportada: é controle de acesso do ERP, não dado de negócio.

## Envelope

```json
{
  "schema_version": "1",
  "tenant_id": "uuid",
  "resource": "visits",
  "generated_at": "2026-10-06T12:00:00Z",
  "offset": 0,
  "limit": 500,
  "next_offset": 500,
  "items": []
}
```

## Sincronização recomendada

### Carga inicial

1. chamar o recurso sem updated_since e sem snapshot_at;
2. guardar generated_at da primeira página;
3. para as páginas seguintes, reenviar esse valor em snapshot_at;
4. continuar usando next_offset até retornar null;
5. ao concluir todas as páginas, guardar generated_at como watermark do recurso.

### Carga incremental

1. enviar updated_since com o watermark anterior;
2. usar generated_at da primeira página como snapshot_at das páginas seguintes;
3. concluir todas as páginas;
4. somente então avançar o watermark para generated_at.

O watermark é por recurso. Não avançar o watermark se uma página falhar.

## Segurança

- somente leitura;
- tenant derivado da credencial;
- chave revogável;
- segredo nunca armazenado em claro;
- chave não aparece novamente na listagem;
- tenant inativo ou chave revogada retorna 401;
- nenhum endpoint de IA existe no ERP;
- nenhuma ferramenta de integração recebe SQL livre.

## Evolução de contrato

Mudanças incompatíveis devem criar uma nova versão de rota, por exemplo /integration/v2.

Campos novos podem ser adicionados de forma compatível dentro da v1 quando não alterarem a semântica existente.
