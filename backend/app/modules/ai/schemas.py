from uuid import UUID

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class ToolTraceItem(BaseModel):
    tool: str
    arguments: dict
    result_count: int | None = None


class AskResponse(BaseModel):
    run_id: UUID
    answer: str
    tool_trace: list[ToolTraceItem]
    provider: str
    model: str
