"""switch search_vector to english dictionary

Stemming + stopword removal so "pockets" matches "pocket" and "with"
isn't required to appear in the indexed text.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-16
"""
from collections.abc import Sequence

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

from alembic import op

ENGLISH_EXPR = """
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(brand, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(category, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(description, '')), 'C')
"""

SIMPLE_EXPR = """
    setweight(to_tsvector('simple', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('simple', coalesce(brand, '')), 'B') ||
    setweight(to_tsvector('simple', coalesce(category, '')), 'B') ||
    setweight(to_tsvector('simple', coalesce(description, '')), 'C')
"""


def _replace_search_vector(expr: str) -> None:
    op.execute("DROP INDEX IF EXISTS ix_products_search_vector")
    op.execute("ALTER TABLE products DROP COLUMN search_vector")
    op.execute(
        f"ALTER TABLE products ADD COLUMN search_vector tsvector "
        f"GENERATED ALWAYS AS ({expr}) STORED"
    )
    op.execute(
        "CREATE INDEX ix_products_search_vector ON products USING gin(search_vector)"
    )


def upgrade() -> None:
    _replace_search_vector(ENGLISH_EXPR)


def downgrade() -> None:
    _replace_search_vector(SIMPLE_EXPR)
