import csv
from datetime import UTC, datetime
from html import escape
from io import StringIO
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select

from app.models.field import (
    Attachment,
    ChecklistTemplateItem,
    Measurement,
    Visit,
    VisitAnswer,
    VisitAssetSituation,
)
from app.models.identity import Membership, Role, User
from app.models.maintenance import MaintenancePlan, Occurrence, VisitReview, WorkOrder
from app.models.operations import Asset, Client, Development, Station
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles
from app.modules.client_portal.service import client_can_view_development

router = APIRouter(prefix="/reports", tags=["relatorios"])

MANAGEMENT_ROLES = (
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
)
ManagementContextDep = Annotated[AuthContext, Depends(require_roles(*MANAGEMENT_ROLES))]


def csv_response(filename: str, headers: list[str], rows: list[list[object]]) -> Response:
    output = StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(headers)
    writer.writerows(rows)
    body = "\ufeff" + output.getvalue()
    return Response(
        body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/visits.csv")
async def visits_csv(
    context: ManagementContextDep,
    session: SessionDep,
) -> Response:
    rows = list(
        (
            await session.execute(
                select(Visit)
                .where(Visit.tenant_id == context.tenant.id)
                .order_by(Visit.scheduled_for.desc())
                .limit(10_000)
            )
        ).scalars()
    )
    return csv_response(
        "visitas.csv",
        [
            "id",
            "station_id",
            "technician_membership_id",
            "scheduled_for",
            "started_at",
            "finished_at",
            "status",
            "notes",
        ],
        [
            [
                item.id,
                item.station_id,
                item.technician_membership_id,
                item.scheduled_for,
                item.started_at or "",
                item.finished_at or "",
                item.status,
                item.notes or "",
            ]
            for item in rows
        ],
    )


@router.get("/work-orders.csv")
async def work_orders_csv(
    context: ManagementContextDep,
    session: SessionDep,
) -> Response:
    rows = list(
        (
            await session.execute(
                select(WorkOrder)
                .where(WorkOrder.tenant_id == context.tenant.id)
                .order_by(WorkOrder.created_at.desc())
                .limit(10_000)
            )
        ).scalars()
    )
    return csv_response(
        "ordens-servico.csv",
        [
            "id",
            "station_id",
            "asset_id",
            "assigned_membership_id",
            "priority",
            "status",
            "sla_due_at",
            "started_at",
            "completed_at",
            "validated_at",
            "description",
        ],
        [
            [
                item.id,
                item.station_id,
                item.asset_id or "",
                item.assigned_membership_id or "",
                item.priority,
                item.status,
                item.sla_due_at,
                item.started_at or "",
                item.completed_at or "",
                item.validated_at or "",
                item.description,
            ]
            for item in rows
        ],
    )


@router.get("/maintenance.csv")
async def maintenance_csv(
    context: ManagementContextDep,
    session: SessionDep,
) -> Response:
    now = datetime.now(UTC)
    rows = list(
        (
            await session.execute(
                select(MaintenancePlan)
                .where(MaintenancePlan.tenant_id == context.tenant.id)
                .order_by(MaintenancePlan.next_due_at)
                .limit(10_000)
            )
        ).scalars()
    )
    return csv_response(
        "manutencao-preventiva.csv",
        [
            "id",
            "asset_id",
            "assigned_membership_id",
            "maintenance_type",
            "frequency_days",
            "next_due_at",
            "last_completed_at",
            "is_overdue",
            "is_active",
            "instructions",
        ],
        [
            [
                item.id,
                item.asset_id,
                item.assigned_membership_id or "",
                item.maintenance_type,
                item.frequency_days,
                item.next_due_at,
                item.last_completed_at or "",
                item.is_active and item.next_due_at < now,
                item.is_active,
                item.instructions or "",
            ]
            for item in rows
        ],
    )


SITUATION_LABELS = {
    "FUNCIONANDO": "Funcionando adequadamente",
    "DESLIGADO": "Desligado (equipamento ok)",
    "NECESSARIO_VERIFICAR": "Necessário verificar",
    "AGUARDANDO_RETIRADA": "Aguardando ser retirado",
    "RETIRADO_AGUARDANDO_MANUTENCAO": "Retirado e aguardando manutenção",
    "EM_MANUTENCAO": "Em manutenção",
    "AGUARDANDO_INSTALACAO": "Aguardando ser instalado",
    "NAO_POSSUI": "Não possui",
    "OUTRO": "Outro",
}

REPORT_ROLES = MANAGEMENT_ROLES + (Role.TECNICO.value, Role.CLIENTE.value)
ReportContextDep = Annotated[AuthContext, Depends(require_roles(*REPORT_ROLES))]


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone().strftime("%d/%m/%Y %H:%M")


def _format_answer(value: object) -> str:
    if value is True:
        return "Sim"
    if value is False:
        return "Não"
    if value is None:
        return "-"
    return str(value)


@router.get("/visits/{visit_id}.html")
async def visit_report_html(
    visit_id: UUID,
    context: ReportContextDep,
    session: SessionDep,
) -> Response:
    visit = (
        await session.execute(
            select(Visit).where(
                Visit.id == visit_id,
                Visit.tenant_id == context.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if visit is None:
        return Response(status_code=404)

    if (
        context.membership.role == Role.TECNICO.value
        and visit.technician_membership_id != context.membership.id
    ):
        return Response(status_code=403)

    station = (
        await session.execute(
            select(Station).where(
                Station.id == visit.station_id,
                Station.tenant_id == context.tenant.id,
            )
        )
    ).scalar_one()
    development = (
        await session.execute(
            select(Development).where(
                Development.id == station.development_id,
                Development.tenant_id == context.tenant.id,
            )
        )
    ).scalar_one()
    client = (
        await session.execute(
            select(Client).where(
                Client.id == development.client_id,
                Client.tenant_id == context.tenant.id,
            )
        )
    ).scalar_one()

    if context.membership.role == Role.CLIENTE.value:
        if visit.status != "REVISADA":
            return Response(status_code=404)
        if not await client_can_view_development(session, context, development.id):
            return Response(status_code=404)
    technician = (
        await session.execute(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.id == visit.technician_membership_id,
                Membership.tenant_id == context.tenant.id,
            )
        )
    ).scalar_one()

    answers = list(
        (
            await session.execute(
                select(VisitAnswer, ChecklistTemplateItem)
                .join(
                    ChecklistTemplateItem,
                    ChecklistTemplateItem.id == VisitAnswer.item_id,
                )
                .where(
                    VisitAnswer.visit_id == visit.id,
                    VisitAnswer.tenant_id == context.tenant.id,
                )
                .order_by(ChecklistTemplateItem.position, ChecklistTemplateItem.label)
            )
        ).all()
    )
    measurements = list(
        (
            await session.execute(
                select(Measurement)
                .where(
                    Measurement.visit_id == visit.id,
                    Measurement.tenant_id == context.tenant.id,
                )
                .order_by(Measurement.measured_at)
            )
        ).scalars()
    )
    occurrences = list(
        (
            await session.execute(
                select(Occurrence)
                .where(
                    Occurrence.visit_id == visit.id,
                    Occurrence.tenant_id == context.tenant.id,
                )
                .order_by(Occurrence.detected_at)
            )
        ).scalars()
    )
    attachments = list(
        (
            await session.execute(
                select(Attachment)
                .where(
                    Attachment.visit_id == visit.id,
                    Attachment.tenant_id == context.tenant.id,
                )
                .order_by(Attachment.created_at)
            )
        ).scalars()
    )
    review = (
        await session.execute(
            select(VisitReview)
            .where(
                VisitReview.visit_id == visit.id,
                VisitReview.tenant_id == context.tenant.id,
            )
            .order_by(VisitReview.reviewed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    checklist_rows = "".join(
        f"<tr><td>{escape(item.label)}</td><td>{escape(_format_answer(answer.value_json))}</td></tr>"
        for answer, item in answers
    ) or '<tr><td colspan="2">Sem respostas registradas.</td></tr>'

    measurement_rows = "".join(
        "<tr>"
        f"<td>{escape(item.measurement_type)}</td>"
        f"<td>{escape(str(item.value) if item.value is not None else '-')}</td>"
        f"<td>{escape(item.unit or '-')}</td>"
        f"<td>{escape(item.status)}</td>"
        f"<td>{escape(item.reason or '-')}</td>"
        "</tr>"
        for item in measurements
    ) or '<tr><td colspan="5">Sem medições registradas.</td></tr>'

    occurrence_rows = "".join(
        "<tr>"
        f"<td>{escape(item.occurrence_type)}</td>"
        f"<td>{escape(item.severity)}</td>"
        f"<td>{escape(item.status)}</td>"
        f"<td>{escape(item.description)}</td>"
        "</tr>"
        for item in occurrences
    ) or '<tr><td colspan="4">Sem ocorrências registradas.</td></tr>'

    # Situacao dos equipamentos e informacao interna: nao vai no relatorio visto pelo cliente.
    asset_section = ""
    if context.membership.role != Role.CLIENTE.value:
        situations = (
            await session.execute(
                select(VisitAssetSituation, Asset)
                .join(Asset, Asset.id == VisitAssetSituation.asset_id)
                .where(
                    VisitAssetSituation.visit_id == visit.id,
                    VisitAssetSituation.tenant_id == context.tenant.id,
                )
                .order_by(Asset.name)
            )
        ).all()
        situation_rows = "".join(
            "<tr>"
            f"<td>{escape(asset.name)}</td>"
            f"<td>{escape(SITUATION_LABELS.get(record.situation, record.situation))}</td>"
            f"<td>{escape(record.comment or '-')}</td>"
            "</tr>"
            for record, asset in situations
        ) or '<tr><td colspan="3">Sem situação de equipamento registrada.</td></tr>'
        asset_section = (
            "  <h2>Situação dos equipamentos</h2>\n"
            "  <table><thead><tr><th>Equipamento</th><th>Situação</th><th>Observação</th></tr>"
            f"</thead><tbody>{situation_rows}</tbody></table>\n"
        )

    evidence_rows = "".join(
        "<tr>"
        f"<td>{escape(item.caption or 'Evidência')}</td>"
        f"<td>{escape(item.content_type)}</td>"
        f"<td>{escape(item.storage_status)}</td>"
        "</tr>"
        for item in attachments
    ) or '<tr><td colspan="3">Sem evidências registradas.</td></tr>'

    review_text = "Aguardando revisão"
    if review is not None:
        review_text = f"{review.decision} em {_format_datetime(review.reviewed_at)}"
        if review.notes:
            review_text += f" - {review.notes}"

    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório de visita - {escape(station.name)}</title>
<style>
  :root {{ font-family: Inter, Arial, sans-serif; color: #172033; }}
  body {{ margin: 0; background: #eef2f6; }}
  main {{ max-width: 920px; margin: 24px auto; background: white; padding: 36px; box-shadow: 0 8px 30px #0001; }}
  header {{ display: flex; justify-content: space-between; gap: 24px; border-bottom: 3px solid #172033; padding-bottom: 18px; }}
  h1 {{ margin: 0; font-size: 28px; }} h2 {{ margin-top: 30px; font-size: 18px; }}
  .muted {{ color: #667085; }} .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px 28px; margin-top: 20px; }}
  .item span {{ display: block; font-size: 12px; color: #667085; text-transform: uppercase; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
  th, td {{ border: 1px solid #d0d5dd; padding: 9px 10px; text-align: left; vertical-align: top; }}
  th {{ background: #f2f4f7; font-size: 12px; text-transform: uppercase; }}
  .validation {{ margin-top: 26px; padding: 16px; background: #f8fafc; border-left: 4px solid #172033; }}
  .print {{ position: fixed; right: 24px; bottom: 24px; padding: 12px 18px; border: 0; border-radius: 8px; background: #172033; color: white; cursor: pointer; }}
  @media print {{ body {{ background: white; }} main {{ margin: 0; max-width: none; box-shadow: none; padding: 0; }} .print {{ display: none; }} }}
</style>
</head>
<body>
<main>
  <header>
    <div><div class="muted">MW Engenharia</div><h1>Relatório de visita técnica</h1></div>
    <div class="muted">ID {escape(str(visit.id))}</div>
  </header>
  <div class="grid">
    <div class="item"><span>Cliente</span><strong>{escape(client.name)}</strong></div>
    <div class="item"><span>Empreendimento</span><strong>{escape(development.name)}</strong></div>
    <div class="item"><span>Estação</span><strong>{escape(station.name)}</strong></div>
    <div class="item"><span>Código</span><strong>{escape(station.code or "-")}</strong></div>
    <div class="item"><span>Técnico</span><strong>{escape(technician.name)}</strong></div>
    <div class="item"><span>Status</span><strong>{escape(visit.status)}</strong></div>
    <div class="item"><span>Agendada</span><strong>{_format_datetime(visit.scheduled_for)}</strong></div>
    <div class="item"><span>Início / fim</span><strong>{_format_datetime(visit.started_at)} / {_format_datetime(visit.finished_at)}</strong></div>
  </div>

{asset_section}
  <h2>Checklist</h2>
  <table><thead><tr><th>Item</th><th>Resposta</th></tr></thead><tbody>{checklist_rows}</tbody></table>

  <h2>Medições</h2>
  <table><thead><tr><th>Tipo</th><th>Valor</th><th>Unidade</th><th>Status</th><th>Observação</th></tr></thead><tbody>{measurement_rows}</tbody></table>

  <h2>Ocorrências</h2>
  <table><thead><tr><th>Tipo</th><th>Criticidade</th><th>Status</th><th>Descrição</th></tr></thead><tbody>{occurrence_rows}</tbody></table>

  <h2>Evidências</h2>
  <table><thead><tr><th>Descrição</th><th>Tipo</th><th>Status</th></tr></thead><tbody>{evidence_rows}</tbody></table>

  <h2>Observações da visita</h2>
  <p>{escape(visit.notes or "Sem observações.")}</p>

  <div class="validation"><strong>Validação:</strong> {escape(review_text)}</div>
</main>
<button class="print" onclick="window.print()">Imprimir / Salvar PDF</button>
</body>
</html>"""

    return Response(
        html,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f'inline; filename="visita-{visit.id}.html"',
            "Cache-Control": "no-store",
        },
    )
