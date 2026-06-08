from sqlalchemy import MetaData, Table, Column, String, Float, Integer, Numeric, Boolean, Date, DateTime, ForeignKey, UniqueConstraint, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
import datetime

# MetaData for the 'rac' schema
metadata = MetaData(schema="rac")

# rac.settings
settings = Table(
    "settings",
    metadata,
    Column("key", String, primary_key=True),
    Column("value", JSONB, nullable=False),
    Column("updated_at", DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow),
)

# rac.zip_geo
zip_geo = Table(
    "zip_geo",
    metadata,
    Column("postal_code", String, nullable=False),
    Column("country", String, nullable=False),
    Column("lat", Numeric, nullable=False),
    Column("lng", Numeric, nullable=False),
    Column("city", String, nullable=True),
    Column("state", String, nullable=True),
    PrimaryKeyConstraint("country", "postal_code"),
)

# rac.carriers
carriers = Table(
    "carriers",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("name", String, unique=True, nullable=False),
    Column("aliases", ARRAY(String), nullable=True),
    Column("created_at", DateTime(timezone=True), default=datetime.datetime.utcnow),
    Column("updated_at", DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow),
    Column("notes", String, nullable=True),
)

# rac.agreements
agreements = Table(
    "agreements",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("carrier_id", UUID(as_uuid=True), ForeignKey("carriers.id", ondelete="CASCADE"), nullable=False),
    Column("source_file_name", String, nullable=False),
    Column("source_file_hash", String, nullable=False),
    Column("version_flag", String, nullable=False),  # 'new', 'old', 'na'
    Column("effective_from", Date, nullable=True),
    Column("effective_to", Date, nullable=True),
    Column("service_level", String, nullable=True),
    Column("uploaded_at", DateTime(timezone=True), default=datetime.datetime.utcnow),
    Column("raw_storage_path", String, nullable=False),
)

# rac.rate_rows
rate_rows = Table(
    "rate_rows",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("agreement_id", UUID(as_uuid=True), ForeignKey("agreements.id", ondelete="CASCADE"), nullable=False),
    Column("carrier_name", String, nullable=False),
    Column("agreement_effective_from", Date, nullable=True),
    Column("agreement_effective_to", Date, nullable=True),
    Column("origin_city", String, nullable=True),
    Column("origin_state", String, nullable=True),
    Column("origin_country", String, nullable=True),
    Column("origin_zip", String, nullable=True),
    Column("origin_zip_range_lo", String, nullable=True),
    Column("origin_zip_range_hi", String, nullable=True),
    Column("dest_city", String, nullable=True),
    Column("dest_state", String, nullable=True),
    Column("dest_country", String, nullable=True),
    Column("dest_zip", String, nullable=True),
    Column("dest_zip_range_lo", String, nullable=True),
    Column("dest_zip_range_hi", String, nullable=True),
    Column("service_level", String, nullable=True),
    Column("weight_break_lo", Float, nullable=True),
    Column("weight_break_hi", Float, nullable=True),
    Column("pallet_break_lo", Integer, nullable=True),
    Column("pallet_break_hi", Integer, nullable=True),
    Column("freight_rate", Numeric, nullable=True),
    Column("freight_rate_unit", String, nullable=True),  # 'per_shipment', 'per_cwt', 'per_mile', 'per_pallet'
    Column("fuel_pct", Numeric, nullable=True),
    Column("fuel_flat", Numeric, nullable=True),
    Column("minimum_charge", Numeric, nullable=True),
    Column("no_rate", Boolean, default=False, nullable=False),
    Column("rate_note", String, nullable=True),
    Column("notes", String, nullable=True),
    Column("source_file", String, nullable=False),
    Column("source_locator", String, nullable=False),
)

# rac.clause_taxonomy
clause_taxonomy = Table(
    "clause_taxonomy",
    metadata,
    Column("code", String, primary_key=True),
    Column("label", String, nullable=False),
    Column("description", String, nullable=True),
    Column("schema", JSONB, nullable=True),
)

# rac.clauses
clauses = Table(
    "clauses",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("agreement_id", UUID(as_uuid=True), ForeignKey("agreements.id", ondelete="CASCADE"), nullable=False),
    Column("clause_type", String, ForeignKey("clause_taxonomy.code"), nullable=False),
    Column("extracted_text", String, nullable=False),
    Column("structured_value", JSONB, nullable=True),
    Column("user_status", String, nullable=False),  # 'accepted', 'rejected', 'edited', 'pending'
    Column("source_locator", String, nullable=True),
)

# rac.clause_favorability_rubric
clause_favorability_rubric = Table(
    "clause_favorability_rubric",
    metadata,
    Column("clause_type", String, ForeignKey("clause_taxonomy.code", ondelete="CASCADE"), primary_key=True),
    Column("criterion", String, nullable=True),
    Column("weight", Numeric, default=1.0, nullable=False),
    Column("shipper_favorable_pattern", JSONB, nullable=True),
    Column("carrier_favorable_pattern", JSONB, nullable=True),
)

# rac.templates
templates = Table(
    "templates",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("name", String, nullable=False),
    Column("scope", String, nullable=False),  # 'comparison', 'analysis'
    Column("payload", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), default=datetime.datetime.utcnow),
    Column("updated_at", DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow),
)
