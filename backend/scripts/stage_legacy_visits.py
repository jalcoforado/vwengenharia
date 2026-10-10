import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.identity import Tenant
from app.modules.legacy_migration.parser import stage_workbook


async def stage_file(tenant_id: str, file_path: Path, sheet_name: str) -> None:
    if not file_path.exists():
        raise RuntimeError(f"file not found: {file_path}")

    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = (
            await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
        ).scalar_one_or_none()
        if tenant is None:
            raise RuntimeError("tenant not found")

        result = await stage_workbook(
            session,
            tenant_id=tenant.id,
            filename=file_path.name,
            content=file_path.read_bytes(),
            sheet_name=sheet_name,
        )
        print(
            json.dumps(
                {
                    "tenant_id": str(tenant.id),
                    **result,
                },
                ensure_ascii=False,
            )
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage legacy MW Engenharia visits from XLSX without normalizing them."
    )
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--sheet", default="Página1")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    await stage_file(args.tenant_id, args.file, args.sheet)


if __name__ == "__main__":
    asyncio.run(main())
