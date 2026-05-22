"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-16

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extensions (idempotent — postgres-init.sql also creates these, but a fresh DB run by
    # alembic alone shouldn't fail).
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "products",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("retailer", sa.String(32), nullable=False),
        sa.Column("retailer_product_id", sa.String(128), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("brand", sa.String(128)),
        sa.Column("category", sa.String(64)),
        sa.Column("description", sa.Text()),
        sa.Column("price", sa.Numeric(10, 2)),
        sa.Column("currency", sa.String(3)),
        sa.Column("original_price", sa.Numeric(10, 2)),
        sa.Column("image_url", sa.Text()),
        sa.Column("colors", postgresql.ARRAY(sa.String())),
        sa.Column("sizes", postgresql.ARRAY(sa.String())),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("in_stock", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('simple', coalesce(title, '')), 'A') || "
                "setweight(to_tsvector('simple', coalesce(brand, '')), 'B') || "
                "setweight(to_tsvector('simple', coalesce(category, '')), 'B') || "
                "setweight(to_tsvector('simple', coalesce(description, '')), 'C')",
                persisted=True,
            ),
        ),
        sa.Column("scraped_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("retailer", "retailer_product_id", name="uq_products_retailer_rpid"),
    )

    op.create_index(
        "ix_products_search_vector",
        "products",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_products_title_trgm",
        "products",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    op.create_index("ix_products_category", "products", ["category"])
    op.create_index("ix_products_brand", "products", ["brand"])
    op.create_index("ix_products_price", "products", ["price"])


def downgrade() -> None:
    op.drop_index("ix_products_price", table_name="products")
    op.drop_index("ix_products_brand", table_name="products")
    op.drop_index("ix_products_category", table_name="products")
    op.drop_index("ix_products_title_trgm", table_name="products")
    op.drop_index("ix_products_search_vector", table_name="products")
    op.drop_table("products")
