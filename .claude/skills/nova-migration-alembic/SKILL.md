---
name: nova-migration-alembic
description: Cria uma migration Alembic no padrão do ERP da MW — numerada em sequência, encadeada na anterior, id de no máximo 32 caracteres, aditiva, com downgrade que funciona e carga de dados que não tira acesso nem histórico de ninguém. Use sempre que uma mudança precisar de coluna, tabela, índice ou ajuste de dados no banco.
---

# Nova migration Alembic

Migrations ficam em `backend/alembic/versions/` e são aplicadas em sequência. Uma migration
errada quebra o CI de todo mundo ou, pior, o banco de quem atualizar.

## 1. Descobrir a anterior

```bash
ls backend/alembic/versions/ | sort | tail -3
grep -h '^revision' backend/alembic/versions/*.py | sort | tail -1
```

Confirme que existe **uma única** ponta: nenhuma outra migration aponta para a última como
`down_revision`. Se houver duas pontas (duas branches criaram a mesma numeração), pare e avise.

## 2. Nomear

- Arquivo: `NNNN_descricao_curta.py`, com `NNNN` = último número + 1.
- `revision` igual ao nome do arquivo sem `.py`.
- **No máximo 32 caracteres** no `revision`: é o tamanho da coluna `alembic_version.version_num`.
  Acima disso a migration roda em teste e quebra no banco real. Encurte a descrição se preciso.

## 3. Escrever

Use `template.py` desta pasta como ponto de partida. Regras:

- **Aditiva por padrão.** Coluna nova é `nullable=True` ou tem `server_default`. Coluna
  obrigatória em tabela com dados precisa de valor padrão ou de carga antes do `NOT NULL`.
- **Toda tabela de negócio tem `tenant_id`** com `ForeignKey("tenants.id", ondelete="CASCADE")`
  e índice. Restrições de unicidade incluem o `tenant_id`.
- **Carga de dados** (`op.execute`) preserva o que existe: ninguém perde acesso, vínculo ou
  histórico. Escreva no comentário o que a carga faz e por quê.
- **`downgrade` de verdade**, na ordem inversa do `upgrade`. Se a carga não puder ser desfeita,
  diga isso no comentário do `downgrade`.
- Atualize o modelo SQLAlchemy em `backend/app/models/` no mesmo commit, com os mesmos tipos,
  tamanhos e nomes de restrição.
- Se a tabela ou coluna é exportada ao iAnalisys, atualize `docs/INTEGRATION_IANALISYS.md`.
- Tabela nova entra na lista de entidades de `docs/SPEC_V1.md`.

## 4. Validar

Rode a skill `validar-ci` (backend). Ela faz `upgrade head`, `downgrade -1` e `upgrade head` de
novo: os três precisam passar. Escreva teste para a regra nova que a migration suporta.

## 5. Aplicar no ambiente local

O serviço `migrate` do compose aplica a migration ao subir o ambiente (skill
`subir-ambiente-local`). Confira na saída a linha `Running upgrade <anterior> -> <nova>`.
