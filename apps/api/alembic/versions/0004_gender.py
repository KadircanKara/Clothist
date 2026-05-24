"""gender column for Men/Women catalog routes

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-24

Adds a single nullable VARCHAR(16) for gender so the /men and /women
catalog routes can filter cleanly. Variants (per-color image URLs) live
in the existing attributes JSONB under attributes.variants[] — no new
column needed there.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE products ADD COLUMN gender VARCHAR(16)")
    op.execute("CREATE INDEX ix_products_gender ON products (gender)")
    op.execute(
        "ALTER TABLE products ADD CONSTRAINT ck_products_gender_enum "
        "CHECK (gender IS NULL OR gender IN ('men','women','unisex'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE products DROP CONSTRAINT IF EXISTS ck_products_gender_enum")
    op.execute("DROP INDEX IF EXISTS ix_products_gender")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS gender")
