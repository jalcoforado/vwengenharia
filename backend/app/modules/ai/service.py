import json
from datetime import UTC, datetime

from anthropic import APIError, AsyncAnthropic
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ai import AiRun
from app.modules.ai.tools import TOOL_DEFINITIONS, execute_tool, result_count
from app.modules.auth.dependencies import AuthContext
from app.modules.core_registers.service import add_audit

SYSTEM_PROMPT = """Voce e a SonIA Operacional da VW Engenharia.
Seu papel e responder perguntas sobre a operacao usando exclusivamente as ferramentas disponibilizadas.

Regras obrigatorias:
- Nunca invente dados operacionais.
- Nunca afirme que consultou algo que nao veio de uma ferramenta.
- Nao execute nem sugira SQL.
- Nao altere registros, nao abra OS, nao feche ocorrencias e nao mude status.
- Quando faltar contexto, use as ferramentas para buscar a estacao ou os indicadores.
- Diferencie fatos observados de inferencias.
- Priorize riscos operacionais, SLA, indisponibilidade de ativos, recorrencia de falhas e visitas pendentes.
- Responda em portugues do Brasil, de forma objetiva e executiva.
- Quando houver risco critico ou SLA vencido, destaque isso claramente.
"""


async def ask_sonia(
    session: AsyncSession,
    context: AuthContext,
    question: str,
) -> AiRun:
    provider = settings.llm_provider.lower().strip()
    model = settings.anthropic_model
    run = AiRun(
        tenant_id=context.tenant.id,
        user_id=context.user.id,
        question=question,
        provider=provider,
        model=model,
        status="RUNNING",
        tool_trace=[],
    )
    session.add(run)
    await session.flush()
    if provider == "disabled":
        run.status = "FAILED"
        run.error_code = "ai_provider_disabled"
        run.completed_at = datetime.now(UTC)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ai_provider_disabled",
        )

    if provider != "anthropic":
        run.status = "FAILED"
        run.error_code = "unsupported_ai_provider"
        run.completed_at = datetime.now(UTC)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="unsupported_ai_provider",
        )

    if not settings.anthropic_api_key:
        run.status = "FAILED"
        run.error_code = "anthropic_api_key_missing"
        run.completed_at = datetime.now(UTC)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="anthropic_api_key_missing",
        )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    messages: list[dict] = [{"role": "user", "content": question}]
    trace: list[dict] = []

    try:
        for _ in range(settings.ai_max_tool_steps):
            response = await client.messages.create(
                model=model,
                max_tokens=settings.ai_max_tokens,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            tool_uses = [block for block in response.content if block.type == "tool_use"]
            if not tool_uses:
                answer_parts = [
                    block.text for block in response.content if block.type == "text"
                ]
                answer = "\n".join(answer_parts).strip()
                if not answer:
                    answer = "Nao foi possivel produzir uma resposta com os dados disponiveis."
                run.answer = answer
                run.status = "COMPLETED"
                run.tool_trace = trace
                run.completed_at = datetime.now(UTC)
                add_audit(
                    session,
                    context,
                    action="AI_ASK",
                    entity_type="ai_run",
                    entity_id=run.id,
                    fields=["question", "answer", "tool_trace"],
                )
                await session.commit()
                await session.refresh(run)
                return run

            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        block.model_dump() if hasattr(block, "model_dump") else block
                        for block in response.content
                    ],
                }
            )
            tool_results = []
            for tool_use in tool_uses:
                args = dict(tool_use.input or {})
                result = await execute_tool(
                    session,
                    context,
                    tool_use.name,
                    args,
                )
                trace.append(
                    {
                        "tool": tool_use.name,
                        "arguments": args,
                        "result_count": result_count(result),
                    }
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        run.status = "FAILED"
        run.error_code = "ai_tool_budget_exceeded"
        run.tool_trace = trace
        run.completed_at = datetime.now(UTC)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ai_tool_budget_exceeded",
        )
    except HTTPException:
        raise
    except (APIError, TypeError, ValueError):
        run.status = "FAILED"
        run.error_code = "ai_provider_error"
        run.tool_trace = trace
        run.completed_at = datetime.now(UTC)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ai_provider_error",
        ) from None


async def get_run(
    session: AsyncSession,
    context: AuthContext,
    run_id,
) -> AiRun:
    run = (
        await session.execute(
            select(AiRun).where(
                AiRun.id == run_id,
                AiRun.tenant_id == context.tenant.id,
                AiRun.user_id == context.user.id,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ai_run_not_found")
    return run
