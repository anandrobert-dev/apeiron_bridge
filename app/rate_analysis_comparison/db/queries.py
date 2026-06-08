from sqlalchemy import select, insert, update, delete, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
import math
from . import models

def get_carriers(conn):
    """Retrieves all carriers."""
    stmt = select(models.carriers).order_by(models.carriers.c.name)
    return [dict(row._asdict()) for row in conn.execute(stmt)]

def get_carrier_by_name(conn, name: str):
    """Retrieves a carrier by name (case-insensitive)."""
    stmt = select(models.carriers).where(models.carriers.c.name.ilike(name))
    row = conn.execute(stmt).first()
    return dict(row._asdict()) if row else None

def create_carrier(conn, id_, name: str, aliases: list = None, notes: str = None):
    """Creates a new carrier record."""
    stmt = insert(models.carriers).values(
        id=id_,
        name=name,
        aliases=aliases or [],
        notes=notes
    )
    conn.execute(stmt)
    return {"id": id_, "name": name, "aliases": aliases, "notes": notes}

def get_settings(conn):
    """Retrieves all settings."""
    stmt = select(models.settings)
    return {row.key: row.value for row in conn.execute(stmt)}

def get_setting(conn, key: str, default=None):
    """Retrieves a setting by key."""
    stmt = select(models.settings.c.value).where(models.settings.c.key == key)
    row = conn.execute(stmt).first()
    return row[0] if row else default

def set_setting(conn, key: str, value):
    """Sets/updates a setting."""
    stmt = pg_insert(models.settings).values(
        key=key,
        value=value
    ).on_conflict_do_update(
        index_elements=["key"],
        set_={"value": value}
    )
    conn.execute(stmt)

def create_agreement(conn, agreement_id, carrier_id, source_file_name: str, source_file_hash: str,
                     version_flag: str, effective_from=None, effective_to=None, service_level: str = None,
                     raw_storage_path: str = ""):
    """Inserts a new agreement record."""
    stmt = insert(models.agreements).values(
        id=agreement_id,
        carrier_id=carrier_id,
        source_file_name=source_file_name,
        source_file_hash=source_file_hash,
        version_flag=version_flag,
        effective_from=effective_from,
        effective_to=effective_to,
        service_level=service_level,
        raw_storage_path=raw_storage_path
    )
    conn.execute(stmt)

def get_agreements_by_carrier(conn, carrier_id):
    """Retrieves agreements for a specific carrier."""
    stmt = select(models.agreements).where(models.agreements.c.carrier_id == carrier_id).order_by(models.agreements.c.uploaded_at.desc())
    return [dict(row._asdict()) for row in conn.execute(stmt)]

def insert_rate_rows(conn, rows: list[dict]):
    """Bulk inserts normalized rate rows."""
    if not rows:
        return
    conn.execute(insert(models.rate_rows), rows)

def get_rate_rows(conn, agreement_id):
    """Retrieves rate rows for a specific agreement."""
    stmt = select(models.rate_rows).where(models.rate_rows.c.agreement_id == agreement_id)
    return [dict(row._asdict()) for row in conn.execute(stmt)]

def insert_clauses(conn, clause_rows: list[dict]):
    """Bulk inserts extracted clause rows."""
    if not clause_rows:
        return
    conn.execute(insert(models.clauses), clause_rows)

def get_clauses(conn, agreement_id):
    """Retrieves clauses for an agreement."""
    stmt = select(models.clauses).where(models.clauses.c.agreement_id == agreement_id)
    return [dict(row._asdict()) for row in conn.execute(stmt)]

def get_clause_taxonomy(conn):
    """Retrieves all clause taxonomy types."""
    stmt = select(models.clause_taxonomy).order_by(models.clause_taxonomy.c.code)
    return [dict(row._asdict()) for row in conn.execute(stmt)]

def get_clause_favorability_rubric(conn):
    """Retrieves favorability rubrics."""
    stmt = select(models.clause_favorability_rubric)
    return [dict(row._asdict()) for row in conn.execute(stmt)]

def get_zip_geo(conn, country: str, postal_code: str):
    """Retrieves latitude and longitude for a postal code."""
    stmt = select(models.zip_geo).where(
        models.zip_geo.c.country.ilike(country),
        models.zip_geo.c.postal_code.ilike(postal_code)
    )
    row = conn.execute(stmt).first()
    return dict(row._asdict()) if row else None

def get_nearby_zips(conn, lat: float, lng: float, radius_miles: float):
    """
    Finds ZIP codes within radius_miles of a given latitude/longitude.
    Uses bounding box pre-filtering for speed and Haversine formula.
    """
    # 1 degree of latitude is approx 69 miles
    delta_lat = radius_miles / 69.0
    # 1 degree of longitude is approx 69 * cos(lat) miles
    cos_lat = math.cos(math.radians(lat))
    if cos_lat > 0:
        delta_lng = radius_miles / (69.0 * cos_lat)
    else:
        delta_lng = 180.0  # fallback near poles
        
    lat_min, lat_max = lat - delta_lat, lat + delta_lat
    lng_min, lng_max = lng - delta_lng, lng + delta_lng

    # SQL query with Haversine formula
    sql = text("""
        SELECT postal_code, country, lat, lng, city, state,
               (3959 * acos(
                   LEAST(1.0, GREATEST(-1.0, 
                       sin(radians(:lat)) * sin(radians(lat)) +
                       cos(radians(:lat)) * cos(radians(lat)) * cos(radians(lng) - radians(:lng))
                   ))
               )) AS distance
        FROM rac.zip_geo
        WHERE lat BETWEEN :lat_min AND :lat_max
          AND lng BETWEEN :lng_min AND :lng_max
          AND (3959 * acos(
                   LEAST(1.0, GREATEST(-1.0, 
                       sin(radians(:lat)) * sin(radians(lat)) +
                       cos(radians(:lat)) * cos(radians(lat)) * cos(radians(lng) - radians(:lng))
                   ))
               )) <= :radius
        ORDER BY distance
    """)
    
    params = {
        "lat": lat,
        "lng": lng,
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lng_min": lng_min,
        "lng_max": lng_max,
        "radius": radius_miles
    }
    
    rows = conn.execute(sql, params).fetchall()
    return [dict(row._asdict()) for row in rows]
