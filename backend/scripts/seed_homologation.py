import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.models.field import (
    ChecklistTemplate,
    ChecklistTemplateItem,
    Measurement,
    Visit,
    VisitAnswer,
    VisitPlan,
)
from app.models.identity import Membership, Role, Tenant, User
from app.models.maintenance import (
    MaintenancePlan,
    Occurrence,
    VisitReview,
    WorkOrder,
    WorkOrderStatusHistory,
)
from app.models.materials import MaterialRequest
from app.models.operations import Asset, AssetType, Client, Development, Station


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


async def get_or_create_user(
    session,
    *,
    tenant: Tenant,
    email: str,
    name: str,
    password: str,
    role: str,
) -> Membership:
    user = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            name=name,
            password_hash=hash_password(password),
        )
        session.add(user)
        await session.flush()
    else:
        # Homologation seed is authoritative for demo credentials.
        # This intentionally resets demo-user credentials so the launcher
        # always displays credentials that actually work.
        user.name = name
        user.password_hash = hash_password(password)
        user.is_active = True
        await session.flush()

    membership = (
        await session.execute(
            select(Membership).where(
                Membership.tenant_id == tenant.id,
                Membership.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        membership = Membership(
            tenant_id=tenant.id,
            user_id=user.id,
            role=role,
            is_active=True,
        )
        session.add(membership)
        await session.flush()
    else:
        membership.role = role
        membership.is_active = True
    return membership


async def main() -> None:
    password = required("HOMOLOGATION_PASSWORD")
    if len(password) < 12:
        raise RuntimeError("HOMOLOGATION_PASSWORD must contain at least 12 characters")

    tenant_slug = os.getenv("HOMOLOGATION_TENANT_SLUG", "vw-homologacao").strip()
    tenant_name = os.getenv(
        "HOMOLOGATION_TENANT_NAME",
        "VW Engenharia - Homologacao",
    ).strip()

    admin_email = os.getenv(
        "HOMOLOGATION_ADMIN_EMAIL",
        "gestor.homologacao@example.com",
    ).strip().lower()
    tech_email = os.getenv(
        "HOMOLOGATION_TECH_EMAIL",
        "tecnico.homologacao@example.com",
    ).strip().lower()
    maintenance_email = os.getenv(
        "HOMOLOGATION_MAINTENANCE_EMAIL",
        "manutencao.homologacao@example.com",
    ).strip().lower()

    now = datetime.now(UTC).replace(microsecond=0)
    session_factory = get_session_factory()

    async with session_factory() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        ).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(name=tenant_name, slug=tenant_slug, is_active=True)
            session.add(tenant)
            await session.flush()

        admin_membership = await get_or_create_user(
            session,
            tenant=tenant,
            email=admin_email,
            name="Gestor Homologacao",
            password=password,
            role=Role.ADMIN.value,
        )
        tech_membership = await get_or_create_user(
            session,
            tenant=tenant,
            email=tech_email,
            name="Tecnico Homologacao",
            password=password,
            role=Role.TECNICO.value,
        )
        maintenance_membership = await get_or_create_user(
            session,
            tenant=tenant,
            email=maintenance_email,
            name="Manutencao Homologacao",
            password=password,
            role=Role.MANUTENCAO.value,
        )

        admin_user = await session.get(User, admin_membership.user_id)
        tech_user = await session.get(User, tech_membership.user_id)

        client = (
            await session.execute(
                select(Client).where(
                    Client.tenant_id == tenant.id,
                    Client.name == "Condominio Demonstracao",
                )
            )
        ).scalar_one_or_none()
        if client is None:
            client = Client(
                tenant_id=tenant.id,
                name="Condominio Demonstracao",
                contact_name="Administracao do Condominio",
                contact_email="contato@example.com",
                contact_phone="(85) 99999-0000",
                is_active=True,
            )
            session.add(client)
            await session.flush()

        development = (
            await session.execute(
                select(Development).where(
                    Development.tenant_id == tenant.id,
                    Development.name == "Residencial Lago Azul",
                )
            )
        ).scalar_one_or_none()
        if development is None:
            development = Development(
                tenant_id=tenant.id,
                client_id=client.id,
                name="Residencial Lago Azul",
                address_line="Av. Demonstracao, 1000",
                city="Fortaleza",
                state="CE",
                postal_code="60000-000",
                is_active=True,
            )
            session.add(development)
            await session.flush()

        station = (
            await session.execute(
                select(Station).where(
                    Station.tenant_id == tenant.id,
                    Station.code == "ETE-HML-001",
                )
            )
        ).scalar_one_or_none()
        if station is None:
            station = Station(
                tenant_id=tenant.id,
                development_id=development.id,
                name="ETE Residencial Lago Azul",
                code="ETE-HML-001",
                station_type="ETE",
                visit_frequency_days=7,
                is_active=True,
            )
            session.add(station)
            await session.flush()

        aerator_type = (
            await session.execute(
                select(AssetType).where(
                    AssetType.tenant_id == tenant.id,
                    AssetType.code == "AER",
                )
            )
        ).scalar_one_or_none()
        if aerator_type is None:
            aerator_type = AssetType(
                tenant_id=tenant.id,
                name="Aerador",
                code="AER",
                is_active=True,
            )
            session.add(aerator_type)
            await session.flush()

        pump_type = (
            await session.execute(
                select(AssetType).where(
                    AssetType.tenant_id == tenant.id,
                    AssetType.code == "BOM",
                )
            )
        ).scalar_one_or_none()
        if pump_type is None:
            pump_type = AssetType(
                tenant_id=tenant.id,
                name="Bomba",
                code="BOM",
                is_active=True,
            )
            session.add(pump_type)
            await session.flush()

        aerator = (
            await session.execute(
                select(Asset).where(
                    Asset.tenant_id == tenant.id,
                    Asset.station_id == station.id,
                    Asset.name == "Aerador I",
                )
            )
        ).scalar_one_or_none()
        if aerator is None:
            aerator = Asset(
                tenant_id=tenant.id,
                station_id=station.id,
                asset_type_id=aerator_type.id,
                name="Aerador I",
                manufacturer="Demo",
                model="AER-100",
                serial_number=f"HML-AER-{tenant_slug}",
                status="AGUARDANDO_MANUTENCAO",
                notes="Ativo demonstrativo para homologacao.",
                is_active=True,
            )
            session.add(aerator)
            await session.flush()

        pump = (
            await session.execute(
                select(Asset).where(
                    Asset.tenant_id == tenant.id,
                    Asset.station_id == station.id,
                    Asset.name == "Bomba de Recirculacao I",
                )
            )
        ).scalar_one_or_none()
        if pump is None:
            pump = Asset(
                tenant_id=tenant.id,
                station_id=station.id,
                asset_type_id=pump_type.id,
                name="Bomba de Recirculacao I",
                manufacturer="Demo",
                model="BOM-200",
                serial_number=f"HML-BOM-{tenant_slug}",
                status="OPERANDO",
                is_active=True,
            )
            session.add(pump)
            await session.flush()

        template = (
            await session.execute(
                select(ChecklistTemplate).where(
                    ChecklistTemplate.tenant_id == tenant.id,
                    ChecklistTemplate.name == "Checklist ETE - Homologacao",
                    ChecklistTemplate.version == 1,
                )
            )
        ).scalar_one_or_none()
        if template is None:
            template = ChecklistTemplate(
                tenant_id=tenant.id,
                name="Checklist ETE - Homologacao",
                version=1,
                is_active=True,
            )
            session.add(template)
            await session.flush()

        items = {
            item.code: item
            for item in (
                await session.execute(
                    select(ChecklistTemplateItem).where(
                        ChecklistTemplateItem.template_id == template.id
                    )
                )
            ).scalars()
        }
        if "GRADE_LIMPA" not in items:
            session.add(
                ChecklistTemplateItem(
                    tenant_id=tenant.id,
                    template_id=template.id,
                    code="GRADE_LIMPA",
                    label="Grade esta limpa?",
                    answer_type="BOOLEAN",
                    required=True,
                    position=10,
                )
            )
        if "CLORACAO" not in items:
            session.add(
                ChecklistTemplateItem(
                    tenant_id=tenant.id,
                    template_id=template.id,
                    code="CLORACAO",
                    label="Cloracao foi efetuada?",
                    answer_type="BOOLEAN",
                    required=True,
                    position=20,
                )
            )
        if "OBS_GERAL" not in items:
            session.add(
                ChecklistTemplateItem(
                    tenant_id=tenant.id,
                    template_id=template.id,
                    code="OBS_GERAL",
                    label="Observacao geral",
                    answer_type="TEXT",
                    required=False,
                    position=30,
                )
            )
        await session.flush()

        plan = (
            await session.execute(
                select(VisitPlan).where(
                    VisitPlan.tenant_id == tenant.id,
                    VisitPlan.station_id == station.id,
                    VisitPlan.technician_membership_id == tech_membership.id,
                )
            )
        ).scalars().first()
        if plan is None:
            plan = VisitPlan(
                tenant_id=tenant.id,
                station_id=station.id,
                technician_membership_id=tech_membership.id,
                checklist_template_id=template.id,
                frequency_days=7,
                start_at=now + timedelta(days=1),
                next_due_at=now + timedelta(days=1),
                is_active=True,
                notes="Plano semanal de homologacao.",
            )
            session.add(plan)
            await session.flush()

        future_visit = (
            await session.execute(
                select(Visit).where(
                    Visit.tenant_id == tenant.id,
                    Visit.visit_plan_id == plan.id,
                    Visit.status == "PROGRAMADA",
                )
            )
        ).scalars().first()
        if future_visit is None:
            future_visit = Visit(
                tenant_id=tenant.id,
                visit_plan_id=plan.id,
                station_id=station.id,
                technician_membership_id=tech_membership.id,
                checklist_template_id=template.id,
                scheduled_for=now + timedelta(days=1),
                status="PROGRAMADA",
                notes="Visita futura para testar o fluxo no tablet/celular.",
            )
            session.add(future_visit)

        reviewed_visit = (
            await session.execute(
                select(Visit).where(
                    Visit.tenant_id == tenant.id,
                    Visit.station_id == station.id,
                    Visit.notes == "Visita historica demonstrativa homologada.",
                )
            )
        ).scalar_one_or_none()
        if reviewed_visit is None:
            reviewed_visit = Visit(
                tenant_id=tenant.id,
                station_id=station.id,
                technician_membership_id=tech_membership.id,
                checklist_template_id=template.id,
                scheduled_for=now - timedelta(days=7),
                started_at=now - timedelta(days=7, hours=2),
                finished_at=now - timedelta(days=7, hours=1),
                status="REVISADA",
                notes="Visita historica demonstrativa homologada.",
            )
            session.add(reviewed_visit)
            await session.flush()

            checklist_items = list(
                (
                    await session.execute(
                        select(ChecklistTemplateItem).where(
                            ChecklistTemplateItem.template_id == template.id
                        )
                    )
                ).scalars()
            )
            for item in checklist_items:
                if item.code in {"GRADE_LIMPA", "CLORACAO"}:
                    value = True
                else:
                    value = "Operacao normal; aerador requer manutencao programada."
                session.add(
                    VisitAnswer(
                        tenant_id=tenant.id,
                        visit_id=reviewed_visit.id,
                        item_id=item.id,
                        value_json=value,
                    )
                )

            session.add(
                Measurement(
                    tenant_id=tenant.id,
                    visit_id=reviewed_visit.id,
                    measurement_type="PH",
                    status="MEASURED",
                    value=Decimal("7.20"),
                    unit="pH",
                    measured_at=reviewed_visit.finished_at,
                )
            )
            session.add(
                VisitReview(
                    tenant_id=tenant.id,
                    visit_id=reviewed_visit.id,
                    reviewer_user_id=admin_user.id,
                    decision="APROVAR",
                    notes="Visita demonstrativa aprovada.",
                    reviewed_at=reviewed_visit.finished_at + timedelta(minutes=20),
                )
            )

        occurrence = (
            await session.execute(
                select(Occurrence).where(
                    Occurrence.tenant_id == tenant.id,
                    Occurrence.station_id == station.id,
                    Occurrence.description == "Aerador I apresenta ruido e necessita manutencao.",
                )
            )
        ).scalar_one_or_none()
        if occurrence is None:
            occurrence = Occurrence(
                tenant_id=tenant.id,
                visit_id=reviewed_visit.id,
                station_id=station.id,
                asset_id=aerator.id,
                occurrence_type="RUIDO_AERADOR",
                severity="ALTA",
                status="ABERTA",
                description="Aerador I apresenta ruido e necessita manutencao.",
                detected_at=now - timedelta(hours=6),
                created_by_user_id=tech_user.id,
            )
            session.add(occurrence)
            await session.flush()

        work_order = (
            await session.execute(
                select(WorkOrder).where(
                    WorkOrder.tenant_id == tenant.id,
                    WorkOrder.occurrence_id == occurrence.id,
                )
            )
        ).scalar_one_or_none()
        if work_order is None:
            work_order = WorkOrder(
                tenant_id=tenant.id,
                occurrence_id=occurrence.id,
                station_id=station.id,
                asset_id=aerator.id,
                assigned_membership_id=maintenance_membership.id,
                priority="ALTA",
                status="PLANEJADA",
                description="Inspecionar Aerador I e eliminar ruido anormal.",
                sla_due_at=now + timedelta(hours=18),
            )
            session.add(work_order)
            await session.flush()
            session.add(
                WorkOrderStatusHistory(
                    tenant_id=tenant.id,
                    work_order_id=work_order.id,
                    from_status=None,
                    to_status="ABERTA",
                    changed_by_user_id=admin_user.id,
                    note="OS demonstrativa criada.",
                    changed_at=now - timedelta(hours=2),
                )
            )
            session.add(
                WorkOrderStatusHistory(
                    tenant_id=tenant.id,
                    work_order_id=work_order.id,
                    from_status="ABERTA",
                    to_status="PLANEJADA",
                    changed_by_user_id=admin_user.id,
                    note="Equipe de manutencao designada.",
                    changed_at=now - timedelta(hours=1),
                )
            )

        material = (
            await session.execute(
                select(MaterialRequest).where(
                    MaterialRequest.tenant_id == tenant.id,
                    MaterialRequest.station_id == station.id,
                    MaterialRequest.item_name == "Mangueira 1 polegada",
                )
            )
        ).scalar_one_or_none()
        if material is None:
            session.add(
                MaterialRequest(
                    tenant_id=tenant.id,
                    station_id=station.id,
                    visit_id=reviewed_visit.id,
                    work_order_id=work_order.id,
                    asset_id=aerator.id,
                    requested_by_user_id=tech_user.id,
                    category="MATERIAL",
                    item_name="Mangueira 1 polegada",
                    quantity=Decimal(2),
                    unit="m",
                    priority="MEDIA",
                    status="APROVADA",
                    notes="Material demonstrativo para o fluxo de suprimentos.",
                )
            )

        maintenance_plan = (
            await session.execute(
                select(MaintenancePlan).where(
                    MaintenancePlan.tenant_id == tenant.id,
                    MaintenancePlan.asset_id == pump.id,
                )
            )
        ).scalar_one_or_none()
        if maintenance_plan is None:
            session.add(
                MaintenancePlan(
                    tenant_id=tenant.id,
                    asset_id=pump.id,
                    assigned_membership_id=maintenance_membership.id,
                    maintenance_type="PREVENTIVA",
                    frequency_days=30,
                    next_due_at=now + timedelta(days=5),
                    instructions="Inspecionar vedacao, ruido, corrente e fixacao.",
                    is_active=True,
                )
            )

        await session.commit()

        print("Homologation dataset ready.")
        print(f"Tenant: {tenant.name} ({tenant.slug})")
        print(f"Admin: {admin_email}")
        print(f"Technician: {tech_email}")
        print(f"Maintenance: {maintenance_email}")
        print("Password: supplied by HOMOLOGATION_PASSWORD (not printed)")


if __name__ == "__main__":
    asyncio.run(main())
