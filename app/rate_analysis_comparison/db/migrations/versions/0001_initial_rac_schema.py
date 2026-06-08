"""initial rac schema

Revision ID: 0001
Revises: 
Create Date: 2026-06-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Create settings table
    op.create_table(
        'settings',
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('key'),
        schema='rac'
    )

    # 2. Create zip_geo table
    op.create_table(
        'zip_geo',
        sa.Column('postal_code', sa.String(), nullable=False),
        sa.Column('country', sa.String(), nullable=False),
        sa.Column('lat', sa.Numeric(), nullable=False),
        sa.Column('lng', sa.Numeric(), nullable=False),
        sa.Column('city', sa.String(), nullable=True),
        sa.Column('state', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('country', 'postal_code'),
        schema='rac'
    )

    # 3. Create carriers table
    op.create_table(
        'carriers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('aliases', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        schema='rac'
    )

    # 4. Create agreements table
    op.create_table(
        'agreements',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('carrier_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_file_name', sa.String(), nullable=False),
        sa.Column('source_file_hash', sa.String(), nullable=False),
        sa.Column('version_flag', sa.String(), nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=True),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('service_level', sa.String(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('raw_storage_path', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['carrier_id'], ['rac.carriers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='rac'
    )

    # 5. Create rate_rows table
    op.create_table(
        'rate_rows',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('agreement_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('carrier_name', sa.String(), nullable=False),
        sa.Column('agreement_effective_from', sa.Date(), nullable=True),
        sa.Column('agreement_effective_to', sa.Date(), nullable=True),
        sa.Column('origin_city', sa.String(), nullable=True),
        sa.Column('origin_state', sa.String(), nullable=True),
        sa.Column('origin_country', sa.String(), nullable=True),
        sa.Column('origin_zip', sa.String(), nullable=True),
        sa.Column('origin_zip_range_lo', sa.String(), nullable=True),
        sa.Column('origin_zip_range_hi', sa.String(), nullable=True),
        sa.Column('dest_city', sa.String(), nullable=True),
        sa.Column('dest_state', sa.String(), nullable=True),
        sa.Column('dest_country', sa.String(), nullable=True),
        sa.Column('dest_zip', sa.String(), nullable=True),
        sa.Column('dest_zip_range_lo', sa.String(), nullable=True),
        sa.Column('dest_zip_range_hi', sa.String(), nullable=True),
        sa.Column('service_level', sa.String(), nullable=True),
        sa.Column('weight_break_lo', sa.Float(), nullable=True),
        sa.Column('weight_break_hi', sa.Float(), nullable=True),
        sa.Column('pallet_break_lo', sa.Integer(), nullable=True),
        sa.Column('pallet_break_hi', sa.Integer(), nullable=True),
        sa.Column('freight_rate', sa.Numeric(), nullable=True),
        sa.Column('freight_rate_unit', sa.String(), nullable=True),
        sa.Column('fuel_pct', sa.Numeric(), nullable=True),
        sa.Column('fuel_flat', sa.Numeric(), nullable=True),
        sa.Column('minimum_charge', sa.Numeric(), nullable=True),
        sa.Column('no_rate', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('rate_note', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('source_file', sa.String(), nullable=False),
        sa.Column('source_locator', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['agreement_id'], ['rac.agreements.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='rac'
    )

    # 6. Create clause_taxonomy table
    op.create_table(
        'clause_taxonomy',
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('schema', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('code'),
        schema='rac'
    )

    # 7. Create clauses table
    op.create_table(
        'clauses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('agreement_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clause_type', sa.String(), nullable=False),
        sa.Column('extracted_text', sa.String(), nullable=False),
        sa.Column('structured_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('user_status', sa.String(), nullable=False),
        sa.Column('source_locator', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['agreement_id'], ['rac.agreements.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['clause_type'], ['rac.clause_taxonomy.code']),
        sa.PrimaryKeyConstraint('id'),
        schema='rac'
    )

    # 8. Create clause_favorability_rubric table
    op.create_table(
        'clause_favorability_rubric',
        sa.Column('clause_type', sa.String(), nullable=False),
        sa.Column('criterion', sa.String(), nullable=True),
        sa.Column('weight', sa.Numeric(), server_default='1.0', nullable=False),
        sa.Column('shipper_favorable_pattern', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('carrier_favorable_pattern', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['clause_type'], ['rac.clause_taxonomy.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('clause_type'),
        schema='rac'
    )

    # 9. Create templates table
    op.create_table(
        'templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('scope', sa.String(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='rac'
    )

def downgrade() -> None:
    op.drop_table('templates', schema='rac')
    op.drop_table('clause_favorability_rubric', schema='rac')
    op.drop_table('clauses', schema='rac')
    op.drop_table('clause_taxonomy', schema='rac')
    op.drop_table('rate_rows', schema='rac')
    op.drop_table('agreements', schema='rac')
    op.drop_table('carriers', schema='rac')
    op.drop_table('zip_geo', schema='rac')
    op.drop_table('settings', schema='rac')
