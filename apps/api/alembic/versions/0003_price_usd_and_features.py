"""price_usd (GENERATED), fx_rate_used, jsonb features index, meta table

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-23

Adds the canonical USD price column derived from native price / per-row FX
rate, a GIN index for JSONB feature filters, and a single-row meta table for
the taxonomy-version cache key.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Snapshot baked into the migration so it runs reproducibly regardless of when
# rates.json on disk is updated. Must mirror data/fx/rates.json at the time
# this migration is authored.
FX_BACKFILL = {
    "USD": "1.0",
    "EUR": "0.92",
    "GBP": "0.79",
    "TRY": "32.20",
    "JPY": "156.0",
    "CAD": "1.37",
    "AUD": "1.51",
}


def upgrade() -> None:
    # 1. Add fx_rate_used as NULLABLE so existing rows can be backfilled.
    op.execute("ALTER TABLE products ADD COLUMN fx_rate_used NUMERIC(12, 6)")

    # 2. Backfill from the hardcoded snapshot for every known currency.
    for code, rate in FX_BACKFILL.items():
        op.execute(
            f"UPDATE products SET fx_rate_used = {rate} WHERE currency = '{code}'"
        )

    # 2.5. Defensive: refuse to proceed if any row still has a NULL rate.
    op.execute(
        """
        DO $$
        DECLARE n INT; offenders TEXT;
        BEGIN
          SELECT COUNT(*) INTO n FROM products WHERE fx_rate_used IS NULL;
          IF n > 0 THEN
            SELECT string_agg(DISTINCT COALESCE(currency, 'NULL'), ', ')
              INTO offenders
              FROM products WHERE fx_rate_used IS NULL;
            RAISE EXCEPTION
              'Migration 0003: % rows with unmapped currency (currencies: %); add an UPDATE row for each and re-run.',
              n, offenders;
          END IF;
        END $$
        """
    )

    # 3. Lock the column NOT NULL + positive.
    op.execute("ALTER TABLE products ALTER COLUMN fx_rate_used SET NOT NULL")
    op.execute(
        "ALTER TABLE products ADD CONSTRAINT ck_products_fx_rate_positive "
        "CHECK (fx_rate_used > 0)"
    )

    # 4. Add the generated USD price column + its index.
    op.execute(
        "ALTER TABLE products ADD COLUMN price_usd NUMERIC(10, 2) "
        "GENERATED ALWAYS AS (price / fx_rate_used) STORED"
    )
    op.execute("CREATE INDEX ix_products_price_usd ON products (price_usd)")

    # 5. JSONB GIN index for the must-have features filter (attributes -> 'features').
    op.execute(
        "CREATE INDEX ix_products_attributes_features "
        "ON products USING GIN ((attributes -> 'features') jsonb_path_ops)"
    )

    # 6. Meta singleton table for taxonomy-version cache invalidation.
    op.execute(
        """
        CREATE TABLE meta (
          id INTEGER PRIMARY KEY DEFAULT 1,
          taxonomy_version BIGINT NOT NULL DEFAULT 1,
          singleton BOOLEAN NOT NULL DEFAULT TRUE UNIQUE,
          CHECK (id = 1)
        )
        """
    )
    op.execute("INSERT INTO meta (id, taxonomy_version, singleton) VALUES (1, 1, true)")

    # 7. Post-migration sanity assertion: every row with a price must have a
    #    derived price_usd.
    op.execute(
        """
        DO $$
        DECLARE n INT;
        BEGIN
          SELECT COUNT(*) INTO n FROM products
            WHERE price IS NOT NULL AND price_usd IS NULL;
          IF n > 0 THEN
            RAISE EXCEPTION
              'Migration 0003: % rows with price but no price_usd — generated column did not fire.', n;
          END IF;
        END $$
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS meta")
    op.execute("DROP INDEX IF EXISTS ix_products_attributes_features")
    op.execute("DROP INDEX IF EXISTS ix_products_price_usd")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS price_usd")
    op.execute("ALTER TABLE products DROP CONSTRAINT IF EXISTS ck_products_fx_rate_positive")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS fx_rate_used")
