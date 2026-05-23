"""Single-row meta table for cache-invalidation counters.

`taxonomy_version` is incremented on every ingest (seed or scrape) so the
in-process facets cache can detect when it's stale without polling the
products table aggregate counts on every request.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from clothist_api.db.session import Base


class Meta(Base):
    __tablename__ = "meta"

    # Single-row sentinel; enforced by a CHECK in the migration.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, server_default=text("1"))
    taxonomy_version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("1"),
    )
    singleton: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        unique=True,
    )
