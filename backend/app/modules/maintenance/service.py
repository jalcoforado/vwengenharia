from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import Role
from app.models.maintenance import MaintenanceExecution, MaintenancePlan
from app.models.operations import Asset
from app.modules.auth.dependencies import AuthContext
from app.modules.core_registers.service import add_audit, tenant_get_or_404
from app.modules.field.service import get_tenant_membership
from app.modules.maintenance.schemas import (
    MaintenanceExecutionCreate,
    MaintenancePlanCreate,
    MaintenancePlanUpdate,
)

FIELD_ROLES = {Role.TECNICO.value, Role.MANUTENCAO.value}


async def create_plan(
    session: AsyncSession,
    context: AuthContext,
    payload: MaintenancePlanCreate,
) -> MaintenancePlan:
    await tenant_get_or_404(session, Asset, context.tenant.id, payload.asset_id)
    if payload.assigned_membership_id is not None:
        member = await get_tenant_membership(
            session, context.tenant.id, payload.assigned_membership_id
        )
        if member.role not in {
            Role.TECNICO.value,
            Role.MANUTENCAO.value,
            Role.SUPERVISOR.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="membership_cannot_receive_maintenance",
            )

    plan = MaintenancePlan(
        tenant_id=context.tenant.id,
        asset_id=payload.asset_id,
        assigned_membership_id=payload.assigned_membership_id,
        maintenance_type=payload.maintenance_type.value,
        frequency_days=payload.frequency_days,
        next_due_at=payload.next_due_at,
        instructions=payload.instructions,
        is_active=True,
    )
    session.add(plan)
    await session.flush()
    add_audit(
        session,
        context,
        action="MAINTENANCE_PLAN_CREATE",
        entity_type="maintenance_plan",
        entity_id=plan.id,
    )
    await session.commit()
    await session.refresh(plan)
    return plan


async def list_plans(
    session: AsyncSession,
    context: AuthContext,
    *,
    overdue_only: bool = False,
    asset_id: UUID | None = None,
    active_only: bool = True,
) -> list[MaintenancePlan]:
    stmt = select(MaintenancePlan).where(
        MaintenancePlan.tenant_id == context.tenant.id
    )
    if context.membership.role in FIELD_ROLES:
        stmt = stmt.where(
            MaintenancePlan.assigned_membership_id == context.membership.id
        )
    if overdue_only:
        stmt = stmt.where(MaintenancePlan.next_due_at < datetime.now(UTC))
    if asset_id is not None:
        stmt = stmt.where(MaintenancePlan.asset_id == asset_id)
    if active_only:
        stmt = stmt.where(MaintenancePlan.is_active.is_(True))
    stmt = stmt.order_by(MaintenancePlan.next_due_at)
    return list((await session.execute(stmt)).scalars().all())


async def update_plan(
    session: AsyncSession,
    context: AuthContext,
    plan_id: UUID,
    payload: MaintenancePlanUpdate,
) -> MaintenancePlan:
    plan = await tenant_get_or_404(
        session, MaintenancePlan, context.tenant.id, plan_id
    )
    changes = payload.model_dump(exclude_unset=True)
    if "assigned_membership_id" in changes and changes["assigned_membership_id"] is not None:
        member = await get_tenant_membership(
            session, context.tenant.id, changes["assigned_membership_id"]
        )
        if member.role not in {
            Role.TECNICO.value,
            Role.MANUTENCAO.value,
            Role.SUPERVISOR.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="membership_cannot_receive_maintenance",
            )
    for field, value in changes.items():
        setattr(plan, field, value)
    add_audit(
        session,
        context,
        action="MAINTENANCE_PLAN_UPDATE",
        entity_type="maintenance_plan",
        entity_id=plan.id,
        fields=sorted(changes.keys()),
    )
    await session.commit()
    await session.refresh(plan)
    return plan


async def create_execution(
    session: AsyncSession,
    context: AuthContext,
    payload: MaintenanceExecutionCreate,
) -> MaintenanceExecution:
    plan = None
    if payload.maintenance_plan_id is not None:
        plan = await tenant_get_or_404(
            session,
            MaintenancePlan,
            context.tenant.id,
            payload.maintenance_plan_id,
        )
        if (
            context.membership.role in FIELD_ROLES
            and plan.assigned_membership_id is not None
            and plan.assigned_membership_id != context.membership.id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="maintenance_plan_not_found",
            )
        asset_id = plan.asset_id
        maintenance_type = plan.maintenance_type
    else:
        asset_id = payload.asset_id
        maintenance_type = payload.maintenance_type.value if payload.maintenance_type else None

    if asset_id is None or maintenance_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="maintenance_execution_source_invalid",
        )
    await tenant_get_or_404(session, Asset, context.tenant.id, asset_id)

    execution = MaintenanceExecution(
        tenant_id=context.tenant.id,
        maintenance_plan_id=payload.maintenance_plan_id,
        work_order_id=payload.work_order_id,
        asset_id=asset_id,
        performed_by_membership_id=context.membership.id,
        maintenance_type=maintenance_type,
        started_at=payload.started_at,
        completed_at=payload.completed_at,
        notes=payload.notes,
    )
    session.add(execution)

    if plan is not None:
        plan.last_completed_at = payload.completed_at
        plan.next_due_at = payload.completed_at + timedelta(days=plan.frequency_days)

    await session.flush()
    add_audit(
        session,
        context,
        action="MAINTENANCE_EXECUTION_CREATE",
        entity_type="maintenance_execution",
        entity_id=execution.id,
    )
    await session.commit()
    await session.refresh(execution)
    return execution


async def list_executions(
    session: AsyncSession,
    context: AuthContext,
    *,
    asset_id: UUID | None = None,
    plan_id: UUID | None = None,
    limit: int = 100,
) -> list[MaintenanceExecution]:
    stmt = select(MaintenanceExecution).where(
        MaintenanceExecution.tenant_id == context.tenant.id
    )
    if context.membership.role in FIELD_ROLES:
        stmt = stmt.where(
            MaintenanceExecution.performed_by_membership_id == context.membership.id
        )
    if asset_id is not None:
        stmt = stmt.where(MaintenanceExecution.asset_id == asset_id)
    if plan_id is not None:
        stmt = stmt.where(MaintenanceExecution.maintenance_plan_id == plan_id)
    stmt = stmt.order_by(MaintenanceExecution.completed_at.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def maintenance_summary(
    session: AsyncSession,
    context: AuthContext,
) -> dict[str, int]:
    tenant_id = context.tenant.id
    now = datetime.now(UTC)
    active_plans = await session.scalar(
        select(func.count(MaintenancePlan.id)).where(
            MaintenancePlan.tenant_id == tenant_id,
            MaintenancePlan.is_active.is_(True),
        )
    )
    overdue_plans = await session.scalar(
        select(func.count(MaintenancePlan.id)).where(
            MaintenancePlan.tenant_id == tenant_id,
            MaintenancePlan.is_active.is_(True),
            MaintenancePlan.next_due_at < now,
        )
    )
    due_next_7_days = await session.scalar(
        select(func.count(MaintenancePlan.id)).where(
            MaintenancePlan.tenant_id == tenant_id,
            MaintenancePlan.is_active.is_(True),
            MaintenancePlan.next_due_at >= now,
            MaintenancePlan.next_due_at <= now + timedelta(days=7),
        )
    )
    executions_last_30_days = await session.scalar(
        select(func.count(MaintenanceExecution.id)).where(
            MaintenanceExecution.tenant_id == tenant_id,
            MaintenanceExecution.completed_at >= now - timedelta(days=30),
        )
    )
    return {
        "active_plans": int(active_plans or 0),
        "overdue_plans": int(overdue_plans or 0),
        "due_next_7_days": int(due_next_7_days or 0),
        "executions_last_30_days": int(executions_last_30_days or 0),
    }
