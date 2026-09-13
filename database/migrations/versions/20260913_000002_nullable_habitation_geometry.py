"""Allow tabular census habitations without coordinates.

Revision ID: 20260913_000002
Revises: 20260913_000001
"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry


revision = "20260913_000002"
down_revision = "20260913_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "habitations",
        "geom",
        existing_type=Geometry(geometry_type="POINT", srid=4326),
        nullable=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    null_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM habitations WHERE geom IS NULL")
    ).scalar_one()
    if null_count:
        raise RuntimeError(
            "Cannot restore habitations.geom NOT NULL while "
            f"{null_count} habitation rows have NULL geometry."
        )
    op.alter_column(
        "habitations",
        "geom",
        existing_type=Geometry(geometry_type="POINT", srid=4326),
        nullable=False,
    )
