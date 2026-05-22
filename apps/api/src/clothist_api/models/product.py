import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Computed,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from clothist_api.db.session import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    retailer: Mapped[str] = mapped_column(String(32), nullable=False)
    retailer_product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    brand: Mapped[str | None] = mapped_column(String(128))
    category: Mapped[str | None] = mapped_column(String(64), index=True)
    description: Mapped[str | None] = mapped_column(Text)

    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    image_url: Mapped[str | None] = mapped_column(Text)
    colors: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    sizes: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    attributes: Mapped[dict | None] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))

    in_stock: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    # Generated tsvector for full-text search. Weights: title=A, brand=B, category=B, desc=C.
    # English dictionary gives stemming (pockets↔pocket) and stopword removal (with, the…).
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
            "setweight(to_tsvector('english', coalesce(brand, '')), 'B') || "
            "setweight(to_tsvector('english', coalesce(category, '')), 'B') || "
            "setweight(to_tsvector('english', coalesce(description, '')), 'C')",
            persisted=True,
        ),
    )

    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("retailer", "retailer_product_id", name="uq_products_retailer_rpid"),
        Index("ix_products_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_products_title_trgm", "title", postgresql_using="gin",
              postgresql_ops={"title": "gin_trgm_ops"}),
        Index("ix_products_brand", "brand"),
        Index("ix_products_price", "price"),
    )
