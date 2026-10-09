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
- developments
- stations
- assets
- visit-plans
- visits
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

### client-contacts

Uma linha por cliente, empreendimento e área de responsabilidade. O cliente é a pessoa que responde por um ou mais empreendimentos; um empreendimento pode ter vários responsáveis.

Correspondência com a dimensão Cliente do iAnalisys:

| Dimensão Cliente | Campo no recurso | Origem no ERP |
| --- | --- | --- |
| id_cliente | client_id | clients.id |
| id_empreendimento | development_id | developments.id |
| escopo_contato | scope | TECNICO, FINANCEIRO, COMERCIAL ou ADMINISTRATIVO |
| nome | name | clients.name |
| funcao | contact_role | clients.contact_role |
| telefone | contact_phone | clients.contact_phone |
| whatsapp | contact_whatsapp | clients.contact_whatsapp |
| email | contact_email | clients.contact_email |

O recurso também traz `id` (do vínculo), `is_active`, `created_at` e `updated_at`.

`updated_at` é o maior entre a alteração do vínculo e a do cliente. Assim, mudar o telefone de um cliente reenvia todas as linhas dele na carga incremental.

O dono do empreendimento continua em `developments.client_id`. O vínculo de responsabilidade é um cadastro à parte e não altera o acesso do perfil CLIENTE ao portal.

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
