"""Add auto knowledge tables

Revision ID: 20260722ak01
Revises: 42e2978c7933
Create Date: 2026-07-22 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260722ak01"
down_revision: Union[str, None] = "42e2978c7933"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "auto_knowledge_job" not in existing_tables:
        op.create_table(
            "auto_knowledge_job",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("user_id", sa.Text(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("target_knowledge_id", sa.Text(), nullable=False),
            sa.Column("source_filter", sa.JSON(), nullable=False),
            sa.Column("schedule", sa.JSON(), nullable=False),
            sa.Column("extractor", sa.JSON(), nullable=False),
            sa.Column("review_policy", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_running", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("last_run_at", sa.BigInteger(), nullable=True),
            sa.Column("next_run_at", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
        )
        op.create_index("ix_auto_knowledge_job_next_run", "auto_knowledge_job", ["next_run_at"])
        op.create_index(
            "ix_auto_knowledge_job_active_running", "auto_knowledge_job", ["is_active", "is_running"]
        )
        op.create_index(
            "ix_auto_knowledge_job_target_knowledge", "auto_knowledge_job", ["target_knowledge_id"]
        )

    if "auto_knowledge_run" not in existing_tables:
        op.create_table(
            "auto_knowledge_run",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("job_id", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False),
            sa.Column("started_at", sa.BigInteger(), nullable=False),
            sa.Column("finished_at", sa.BigInteger(), nullable=True),
            sa.Column("input_count", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("cleaned_count", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("generated_count", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("duplicate_count", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("failed_count", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("published_count", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["auto_knowledge_job.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_auto_knowledge_run_job_created", "auto_knowledge_run", ["job_id", "created_at"])
        op.create_index("ix_auto_knowledge_run_status", "auto_knowledge_run", ["status"])

    if "auto_knowledge_candidate" not in existing_tables:
        op.create_table(
            "auto_knowledge_candidate",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("job_id", sa.Text(), nullable=False),
            sa.Column("run_id", sa.Text(), nullable=False),
            sa.Column("target_knowledge_id", sa.Text(), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("answer", sa.Text(), nullable=False),
            sa.Column("category", sa.Text(), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("confidence", sa.BigInteger(), nullable=False),
            sa.Column("risk_level", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False),
            sa.Column("duplicate_of", sa.Text(), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("published_file_id", sa.Text(), nullable=True),
            sa.Column("reviewed_by", sa.Text(), nullable=True),
            sa.Column("reviewed_at", sa.BigInteger(), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["auto_knowledge_job.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["run_id"], ["auto_knowledge_run.id"], ondelete="CASCADE"),
        )
        op.create_index(
            "ix_auto_knowledge_candidate_job_status", "auto_knowledge_candidate", ["job_id", "status"]
        )
        op.create_index(
            "ix_auto_knowledge_candidate_target_status",
            "auto_knowledge_candidate",
            ["target_knowledge_id", "status"],
        )
        op.create_index("ix_auto_knowledge_candidate_run", "auto_knowledge_candidate", ["run_id"])

    if "auto_knowledge_source" not in existing_tables:
        op.create_table(
            "auto_knowledge_source",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("candidate_id", sa.Text(), nullable=False),
            sa.Column("chat_id", sa.Text(), nullable=False),
            sa.Column("message_id", sa.Text(), nullable=False),
            sa.Column("user_id", sa.Text(), nullable=False),
            sa.Column("role", sa.Text(), nullable=False),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(["candidate_id"], ["auto_knowledge_candidate.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_auto_knowledge_source_candidate", "auto_knowledge_source", ["candidate_id"])
        op.create_index("ix_auto_knowledge_source_chat", "auto_knowledge_source", ["chat_id"])


def downgrade() -> None:
    op.drop_index("ix_auto_knowledge_source_chat", table_name="auto_knowledge_source")
    op.drop_index("ix_auto_knowledge_source_candidate", table_name="auto_knowledge_source")
    op.drop_table("auto_knowledge_source")

    op.drop_index("ix_auto_knowledge_candidate_run", table_name="auto_knowledge_candidate")
    op.drop_index("ix_auto_knowledge_candidate_target_status", table_name="auto_knowledge_candidate")
    op.drop_index("ix_auto_knowledge_candidate_job_status", table_name="auto_knowledge_candidate")
    op.drop_table("auto_knowledge_candidate")

    op.drop_index("ix_auto_knowledge_run_status", table_name="auto_knowledge_run")
    op.drop_index("ix_auto_knowledge_run_job_created", table_name="auto_knowledge_run")
    op.drop_table("auto_knowledge_run")

    op.drop_index("ix_auto_knowledge_job_target_knowledge", table_name="auto_knowledge_job")
    op.drop_index("ix_auto_knowledge_job_active_running", table_name="auto_knowledge_job")
    op.drop_index("ix_auto_knowledge_job_next_run", table_name="auto_knowledge_job")
    op.drop_table("auto_knowledge_job")
