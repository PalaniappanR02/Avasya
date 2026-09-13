"""Initial AVASYA schema

Revision ID: 20260913_000001
Revises:
Create Date: 2026-09-13 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision = "20260913_000001"
down_revision = None
branch_labels = None
depends_on = None

data_origin = sa.Enum("REAL", "MIXED", "SYNTHETIC_DEMO", name="data_origin")
risk_level = sa.Enum("LOW", "MEDIUM", "HIGH", name="risk_level")
recommendation_action = sa.Enum("APPROVED", "REJECTED", "OVERRIDDEN", name="recommendation_action")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
 
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=True),
        sa.Column("data_origin", data_origin, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("char_length(email) > 0", name="ck_users_email_not_empty"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "habitations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("village_or_ward", sa.String(length=255), nullable=True),
        sa.Column("district", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("geom", Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False),
        sa.Column("population", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("households", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("data_origin", data_origin, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_habitations_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("population >= 0", name="ck_habitations_population_non_negative"),
        sa.CheckConstraint("households >= 0", name="ck_habitations_households_non_negative"),
    )
    op.create_index("ix_habitations_user_id", "habitations", ["user_id"], unique=False)
    op.create_index("ix_habitations_geom", "habitations", ["geom"], unique=False, postgresql_using="gist")

    op.create_table(
        "hazards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hazard_type", sa.String(length=100), nullable=False),
        sa.Column("hazard_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity_score", sa.Float(), nullable=True),
        sa.Column("probability_score", sa.Float(), nullable=True),
        sa.Column("geom", Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True),
        sa.Column("data_origin", data_origin, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("severity_score >= 0 AND severity_score <= 100", name="ck_hazards_severity_score_range"),
        sa.CheckConstraint("probability_score >= 0 AND probability_score <= 100", name="ck_hazards_probability_score_range"),
    )
    op.create_index("ix_hazards_geom", "hazards", ["geom"], unique=False, postgresql_using="gist")

    op.create_table(
        "habitation_hazards",
        sa.Column("habitation_id", sa.Integer(), nullable=False),
        sa.Column("hazard_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["habitation_id"], ["habitations.id"], name="fk_habitation_hazards_habitation_id_habitations", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hazard_id"], ["hazards.id"], name="fk_habitation_hazards_hazard_id_hazards", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("habitation_id", "hazard_id"),
    )
    op.create_index("ix_habitation_hazards_habitation_id", "habitation_hazards", ["habitation_id"], unique=False)
    op.create_index("ix_habitation_hazards_hazard_id", "habitation_hazards", ["hazard_id"], unique=False)

    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("habitation_id", sa.Integer(), nullable=False),
        sa.Column("hazard_id", sa.Integer(), nullable=True),
        sa.Column("assessor_user_id", sa.Integer(), nullable=True),
        sa.Column("overall_risk_score", sa.Float(), nullable=False),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(length=100), nullable=True),
        sa.Column("calculation_details", sa.JSON(), nullable=True),
        sa.Column("input_snapshot", sa.JSON(), nullable=True),
        sa.Column("normalized_values", sa.JSON(), nullable=True),
        sa.Column("weights", sa.JSON(), nullable=True),
        sa.Column("contributions", sa.JSON(), nullable=True),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("freshness", sa.JSON(), nullable=True),
        sa.Column("data_quality", sa.JSON(), nullable=True),
        sa.Column("data_origin", data_origin, nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["habitation_id"], ["habitations.id"], name="fk_risk_assessments_habitation_id_habitations", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hazard_id"], ["hazards.id"], name="fk_risk_assessments_hazard_id_hazards", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assessor_user_id"], ["users.id"], name="fk_risk_assessments_assessor_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("overall_risk_score >= 0 AND overall_risk_score <= 100", name="ck_risk_assessment_score_range"),
        sa.CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_risk_assessment_confidence_range"),
    )
    op.create_index("ix_risk_assessments_habitation_id", "risk_assessments", ["habitation_id"], unique=False)
    op.create_index("ix_risk_assessments_hazard_id", "risk_assessments", ["hazard_id"], unique=False)
    op.create_index("ix_risk_assessments_assessor_user_id", "risk_assessments", ["assessor_user_id"], unique=False)

    op.create_table(
        "evidence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("habitation_id", sa.Integer(), nullable=True),
        sa.Column("hazard_id", sa.Integer(), nullable=True),
        sa.Column("risk_assessment_id", sa.Integer(), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("evidence_type", sa.String(length=120), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("evidence_payload", sa.JSON(), nullable=True),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("data_origin", data_origin, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["habitation_id"], ["habitations.id"], name="fk_evidence_habitation_id_habitations", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["hazard_id"], ["hazards.id"], name="fk_evidence_hazard_id_hazards", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["risk_assessment_id"], ["risk_assessments.id"], name="fk_evidence_risk_assessment_id_risk_assessments", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("char_length(source_name) > 0", name="ck_evidence_source_name_not_empty"),
    )
    op.create_index("ix_evidence_habitation_id", "evidence", ["habitation_id"], unique=False)
    op.create_index("ix_evidence_hazard_id", "evidence", ["hazard_id"], unique=False)
    op.create_index("ix_evidence_risk_assessment_id", "evidence", ["risk_assessment_id"], unique=False)

    op.create_table(
        "destinations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("destination_type", sa.String(length=100), nullable=True),
        sa.Column("district", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=255), nullable=True),
        sa.Column("geom", Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False),
        sa.Column("capacity_total", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("capacity_available", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("data_origin", data_origin, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("capacity_total >= 0", name="ck_destinations_capacity_total_non_negative"),
        sa.CheckConstraint("capacity_available >= 0", name="ck_destinations_capacity_available_non_negative"),
        sa.CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="ck_destinations_risk_score_range"),
    )
    op.create_index("ix_destinations_geom", "destinations", ["geom"], unique=False, postgresql_using="gist")

    op.create_table(
        "relocation_priorities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("habitation_id", sa.Integer(), nullable=False),
        sa.Column("destination_id", sa.Integer(), nullable=True),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("priority_label", sa.String(length=50), nullable=True),
        sa.Column("rationale", sa.JSON(), nullable=True),
        sa.Column("data_origin", data_origin, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_relocation_priorities_user_id_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["habitation_id"], ["habitations.id"], name="fk_relocation_priorities_habitation_id_habitations", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["destination_id"], ["destinations.id"], name="fk_relocation_priorities_destination_id_destinations", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("priority_score >= 0 AND priority_score <= 100", name="ck_relocation_priority_score_range"),
    )
    op.create_index("ix_relocation_priorities_user_id", "relocation_priorities", ["user_id"], unique=False)
    op.create_index("ix_relocation_priorities_habitation_id", "relocation_priorities", ["habitation_id"], unique=False)
    op.create_index("ix_relocation_priorities_destination_id", "relocation_priorities", ["destination_id"], unique=False)

    op.create_table(
        "capacity_assessments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("destination_id", sa.Integer(), nullable=False),
        sa.Column("habitation_id", sa.Integer(), nullable=False),
        sa.Column("assessed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("nominal_capacity", sa.Integer(), nullable=False),
        sa.Column("existing_occupancy", sa.Integer(), nullable=False),
        sa.Column("water_constraint", sa.Float(), nullable=True),
        sa.Column("sanitation_constraint", sa.Float(), nullable=True),
        sa.Column("safety_reserve", sa.Float(), nullable=True),
        sa.Column("required_capacity", sa.Integer(), nullable=False),
        sa.Column("usable_capacity", sa.Integer(), nullable=False),
        sa.Column("capacity_gap", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("assessment_details", sa.JSON(), nullable=True),
        sa.Column("data_origin", data_origin, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["destination_id"], ["destinations.id"], name="fk_capacity_assessments_destination_id_destinations", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["habitation_id"], ["habitations.id"], name="fk_capacity_assessments_habitation_id_habitations", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessed_by_user_id"], ["users.id"], name="fk_capacity_assessments_assessed_by_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("nominal_capacity >= 0", name="ck_capacity_assessment_nominal_capacity_non_negative"),
        sa.CheckConstraint("existing_occupancy >= 0", name="ck_capacity_assessment_existing_occupancy_non_negative"),
        sa.CheckConstraint("required_capacity >= 0", name="ck_capacity_assessment_required_capacity_non_negative"),
        sa.CheckConstraint("usable_capacity >= 0", name="ck_capacity_assessment_usable_capacity_non_negative"),
        sa.CheckConstraint("water_constraint >= 0 AND water_constraint <= 100", name="ck_capacity_assessment_water_constraint_range"),
        sa.CheckConstraint("sanitation_constraint >= 0 AND sanitation_constraint <= 100", name="ck_capacity_assessment_sanitation_constraint_range"),
        sa.CheckConstraint("safety_reserve >= 0", name="ck_capacity_assessment_safety_reserve_non_negative"),
    )
    op.create_index("ix_capacity_assessments_destination_id", "capacity_assessments", ["destination_id"], unique=False)
    op.create_index("ix_capacity_assessments_habitation_id", "capacity_assessments", ["habitation_id"], unique=False)
    op.create_index("ix_capacity_assessments_assessed_by_user_id", "capacity_assessments", ["assessed_by_user_id"], unique=False)

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("risk_assessment_id", sa.Integer(), nullable=True),
        sa.Column("destination_id", sa.Integer(), nullable=True),
        sa.Column("relocation_priority_id", sa.Integer(), nullable=True),
        sa.Column("recommendation_type", sa.String(length=100), nullable=True),
        sa.Column("summary", sa.String(length=255), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("data_origin", data_origin, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["risk_assessment_id"], ["risk_assessments.id"], name="fk_recommendations_risk_assessment_id_risk_assessments", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["destination_id"], ["destinations.id"], name="fk_recommendations_destination_id_destinations", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["relocation_priority_id"], ["relocation_priorities.id"], name="fk_recommendations_relocation_priority_id_relocation_priorities", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_recommendation_confidence_score_range"),
    )
    op.create_index("ix_recommendations_risk_assessment_id", "recommendations", ["risk_assessment_id"], unique=False)
    op.create_index("ix_recommendations_destination_id", "recommendations", ["destination_id"], unique=False)
    op.create_index("ix_recommendations_relocation_priority_id", "recommendations", ["relocation_priority_id"], unique=False)

    op.create_table(
        "recommendation_approvals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column("officer_user_id", sa.Integer(), nullable=False),
        sa.Column("action", recommendation_action, nullable=False),
        sa.Column("original_recommendation", sa.JSON(), nullable=True),
        sa.Column("final_destination_id", sa.Integer(), nullable=True),
        sa.Column("override_note", sa.Text(), nullable=True),
        sa.Column("data_origin", data_origin, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], name="fk_recommendation_approvals_recommendation_id_recommendations", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["officer_user_id"], ["users.id"], name="fk_recommendation_approvals_officer_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["final_destination_id"], ["destinations.id"], name="fk_recommendation_approvals_final_destination_id_destinations", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recommendation_approvals_recommendation_id", "recommendation_approvals", ["recommendation_id"], unique=False)
    op.create_index("ix_recommendation_approvals_officer_user_id", "recommendation_approvals", ["officer_user_id"], unique=False)
    op.create_index("ix_recommendation_approvals_final_destination_id", "recommendation_approvals", ["final_destination_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_recommendation_approvals_final_destination_id", table_name="recommendation_approvals")
    op.drop_index("ix_recommendation_approvals_officer_user_id", table_name="recommendation_approvals")
    op.drop_index("ix_recommendation_approvals_recommendation_id", table_name="recommendation_approvals")
    op.drop_table("recommendation_approvals")

    op.drop_index("ix_recommendations_relocation_priority_id", table_name="recommendations")
    op.drop_index("ix_recommendations_destination_id", table_name="recommendations")
    op.drop_index("ix_recommendations_risk_assessment_id", table_name="recommendations")
    op.drop_table("recommendations")

    op.drop_index("ix_capacity_assessments_assessed_by_user_id", table_name="capacity_assessments")
    op.drop_index("ix_capacity_assessments_habitation_id", table_name="capacity_assessments")
    op.drop_index("ix_capacity_assessments_destination_id", table_name="capacity_assessments")
    op.drop_table("capacity_assessments")

    op.drop_index("ix_relocation_priorities_destination_id", table_name="relocation_priorities")
    op.drop_index("ix_relocation_priorities_habitation_id", table_name="relocation_priorities")
    op.drop_index("ix_relocation_priorities_user_id", table_name="relocation_priorities")
    op.drop_table("relocation_priorities")

    op.drop_index("ix_destinations_geom", table_name="destinations")
    op.drop_table("destinations")

    op.drop_index("ix_evidence_risk_assessment_id", table_name="evidence")
    op.drop_index("ix_evidence_hazard_id", table_name="evidence")
    op.drop_index("ix_evidence_habitation_id", table_name="evidence")
    op.drop_table("evidence")

    op.drop_index("ix_risk_assessments_assessor_user_id", table_name="risk_assessments")
    op.drop_index("ix_risk_assessments_hazard_id", table_name="risk_assessments")
    op.drop_index("ix_risk_assessments_habitation_id", table_name="risk_assessments")
    op.drop_table("risk_assessments")

    op.drop_index("ix_habitation_hazards_hazard_id", table_name="habitation_hazards")
    op.drop_index("ix_habitation_hazards_habitation_id", table_name="habitation_hazards")
    op.drop_table("habitation_hazards")

    op.drop_index("ix_hazards_geom", table_name="hazards")
    op.drop_table("hazards")

    op.drop_index("ix_habitations_geom", table_name="habitations")
    op.drop_index("ix_habitations_user_id", table_name="habitations")
    op.drop_table("habitations")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    recommendation_action.drop(op.get_bind(), checkfirst=True)
    risk_level.drop(op.get_bind(), checkfirst=True)
    data_origin.drop(op.get_bind(), checkfirst=True)

    # PostGIS is shared infrastructure; leave the extension installed.
