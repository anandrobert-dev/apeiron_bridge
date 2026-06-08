import os
import json
from sqlalchemy import text
from app.rate_analysis_comparison.db.engine import get_engine
from app.rate_analysis_comparison.db import models

TAXONOMY_JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "clauses",
    "taxonomy_seed.json"
)

RUBRIC_JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "clauses",
    "rubric_seed.json"
)

# Standard geographic centroids for testing and demonstration (avoiding bloated downloads)
GEO_SEED_DATA = [
    # Canada Postal Code prefixes (First 3 digits)
    {"postal_code": "K8V", "country": "CA", "lat": 44.10, "lng": -77.58, "city": "Trenton", "state": "ON"},
    {"postal_code": "R3C", "country": "CA", "lat": 49.89, "lng": -97.13, "city": "Winnipeg", "state": "MB"},
    {"postal_code": "T2P", "country": "CA", "lat": 51.05, "lng": -114.07, "city": "Calgary", "state": "AB"},
    {"postal_code": "V1Y", "country": "CA", "lat": 49.88, "lng": -119.49, "city": "Kelowna", "state": "BC"},
    {"postal_code": "M5V", "country": "CA", "lat": 43.65, "lng": -79.38, "city": "Toronto", "state": "ON"},
    {"postal_code": "H3B", "country": "CA", "lat": 45.50, "lng": -73.56, "city": "Montreal", "state": "QC"},
    {"postal_code": "V6B", "country": "CA", "lat": 49.28, "lng": -123.11, "city": "Vancouver", "state": "BC"},
    
    # US Zip codes (5 digits)
    {"postal_code": "60601", "country": "US", "lat": 41.87, "lng": -87.62, "city": "Chicago", "state": "IL"},
    {"postal_code": "75201", "country": "US", "lat": 32.77, "lng": -96.79, "city": "Dallas", "state": "TX"},
    {"postal_code": "55987", "country": "US", "lat": 44.05, "lng": -91.64, "city": "Winona", "state": "MN"},
    {"postal_code": "10001", "country": "US", "lat": 40.75, "lng": -73.99, "city": "New York", "state": "NY"},
    {"postal_code": "98101", "country": "US", "lat": 47.60, "lng": -122.33, "city": "Seattle", "state": "WA"},
]

def seed_db():
    print("🌱 Seeding database reference data...")
    engine = get_engine()
    
    with engine.begin() as conn:
        # 1. Settings Seeding
        settings_to_seed = {
            "nearby_lane_radius_miles": 50.0,
            "fuel_default_method": "percentage",
            "currency_default": "USD"
        }
        for k, v in settings_to_seed.items():
            conn.execute(
                text("""
                    INSERT INTO rac.settings (key, value, updated_at)
                    VALUES (:key, :value, NOW())
                    ON CONFLICT (key) DO UPDATE SET value = :value, updated_at = NOW();
                """),
                {"key": k, "value": json.dumps(v)}
            )
        print("  - Seeded settings.")

        # 2. Clause Taxonomy Seeding
        if os.path.exists(TAXONOMY_JSON_PATH):
            with open(TAXONOMY_JSON_PATH, "r", encoding="utf-8") as f:
                taxonomy_items = json.load(f)
                
            for item in taxonomy_items:
                conn.execute(
                    text("""
                        INSERT INTO rac.clause_taxonomy (code, label, description, schema)
                        VALUES (:code, :label, :description, :schema)
                        ON CONFLICT (code) DO UPDATE 
                        SET label = :label, description = :description, schema = :schema;
                    """),
                    {
                        "code": item["code"],
                        "label": item["label"],
                        "description": item.get("description", ""),
                        "schema": json.dumps(item.get("schema", {}))
                    }
                )
            print(f"  - Seeded {len(taxonomy_items)} clause taxonomy records.")
        else:
            print(f"  ⚠️ Warning: taxonomy_seed.json not found at {TAXONOMY_JSON_PATH}")

        # 3. Clause Favorability Rubric Seeding
        if os.path.exists(RUBRIC_JSON_PATH):
            with open(RUBRIC_JSON_PATH, "r", encoding="utf-8") as f:
                rubric_items = json.load(f)
                
            for item in rubric_items:
                conn.execute(
                    text("""
                        INSERT INTO rac.clause_favorability_rubric 
                        (clause_type, criterion, weight, shipper_favorable_pattern, carrier_favorable_pattern)
                        VALUES (:clause_type, :criterion, :weight, :shipper, :carrier)
                        ON CONFLICT (clause_type) DO UPDATE
                        SET criterion = :criterion, weight = :weight, 
                            shipper_favorable_pattern = :shipper, carrier_favorable_pattern = :carrier;
                    """),
                    {
                        "clause_type": item["clause_type"],
                        "criterion": item.get("criterion", ""),
                        "weight": item.get("weight", 1.0),
                        "shipper": json.dumps(item.get("shipper_favorable_pattern", {})),
                        "carrier": json.dumps(item.get("carrier_favorable_pattern", {}))
                    }
                )
            print(f"  - Seeded {len(rubric_items)} favorability rubric entries.")
        else:
            print(f"  ⚠️ Warning: rubric_seed.json not found at {RUBRIC_JSON_PATH}")

        # 4. Zip Geo Centroid Seeding
        for item in GEO_SEED_DATA:
            conn.execute(
                text("""
                    INSERT INTO rac.zip_geo (postal_code, country, lat, lng, city, state)
                    VALUES (:postal_code, :country, :lat, :lng, :city, :state)
                    ON CONFLICT (country, postal_code) DO UPDATE
                    SET lat = :lat, lng = :lng, city = :city, state = :state;
                """),
                item
            )
        print(f"  - Seeded {len(GEO_SEED_DATA)} high-priority geographic centroids.")

    print("✅ Database seeding complete.")

if __name__ == "__main__":
    seed_db()
