from app.models import Base


def test_foundation_tables_are_registered() -> None:
    assert {
        "tenants",
        "users",
        "memberships",
        "refresh_tokens",
        "audit_events",
    }.issubset(Base.metadata.tables)
