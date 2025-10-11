# app.py
from flask import Flask, jsonify, abort, send_file
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError

_engine = None

def get_engine():
    global _engine
    if _engine is not None:
        return _engine
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("Missing DB_URL (or DATABASE_URL) environment variable.")
    # Normalize old 'postgres://' scheme to 'postgresql://'
    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]
    _engine = create_engine(
        db_url,
        pool_pre_ping=True,
    )
    return _engine

def create_app():
    app = Flask(__name__)

    @app.get("/", endpoint="health")
    def health():
        return "<p>Server working!</p>"

    @app.get("/img", endpoint="show_img")
    def show_img():
        return send_file("amygdala.gif", mimetype="image/gif")

    @app.get("/terms/<term>/studies", endpoint="terms_studies")
    def get_studies_by_term(term):
        return term

    @app.get("/locations/<coords>/studies", endpoint="locations_studies")
    def get_studies_by_coordinates(coords):
        x, y, z = map(int, coords.split("_"))
        return jsonify([x, y, z])

    @app.get("/dissociate/terms/<term_a>/<term_b>", endpoint="dissociate_terms")
    def dissociate_by_terms(term_a, term_b):
        """
        Returns studies that mention term_a but NOT term_b.
        Includes bidirectional analysis (A-B and B-A).
        """
        try:
            eng = get_engine()
            with eng.begin() as conn:
                # Ensure we are in the correct schema
                conn.execute(text("SET search_path TO ns, public;"))
                
                # Studies with term_a but not term_b
                a_not_b_query = text("""
                    SELECT DISTINCT a1.study_id 
                    FROM ns.annotations_terms a1 
                    WHERE LOWER(a1.term) = LOWER(:term_a)
                      AND a1.study_id NOT IN (
                        SELECT study_id FROM ns.annotations_terms 
                        WHERE LOWER(term) = LOWER(:term_b)
                      )
                    ORDER BY a1.study_id
                """)
                
                # Studies with term_b but not term_a  
                b_not_a_query = text("""
                    SELECT DISTINCT a1.study_id 
                    FROM ns.annotations_terms a1 
                    WHERE LOWER(a1.term) = LOWER(:term_b)
                      AND a1.study_id NOT IN (
                        SELECT study_id FROM ns.annotations_terms 
                        WHERE LOWER(term) = LOWER(:term_a)
                      )
                    ORDER BY a1.study_id
                """)
                
                a_not_b_results = conn.execute(a_not_b_query, {
                    "term_a": term_a.replace("_", " "), 
                    "term_b": term_b.replace("_", " ")
                }).fetchall()
                
                b_not_a_results = conn.execute(b_not_a_query, {
                    "term_a": term_a.replace("_", " "), 
                    "term_b": term_b.replace("_", " ")
                }).fetchall()
                
                return jsonify({
                    "query": {
                        "term_a": term_a.replace("_", " "),
                        "term_b": term_b.replace("_", " ")
                    },
                    "results": {
                        f"{term_a}_not_{term_b}": {
                            "count": len(a_not_b_results),
                            "studies": [row[0] for row in a_not_b_results]
                        },
                        f"{term_b}_not_{term_a}": {
                            "count": len(b_not_a_results), 
                            "studies": [row[0] for row in b_not_a_results]
                        }
                    }
                })
                
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.get("/dissociate/locations/<coords_a>/<coords_b>", endpoint="dissociate_locations")
    def dissociate_by_coordinates(coords_a, coords_b):
        """
        Returns studies that have activation at coords_a but NOT at coords_b.
        Coordinates format: x_y_z (e.g., "0_-52_26")
        Includes bidirectional analysis.
        """
        try:
            # Parse coordinates
            x1, y1, z1 = map(float, coords_a.split("_"))
            x2, y2, z2 = map(float, coords_b.split("_"))
            
            # Default tolerance for coordinate matching (in mm)
            tolerance = 8.0  # 8mm sphere around each coordinate
            
            eng = get_engine()
            with eng.begin() as conn:
                # Ensure we are in the correct schema
                conn.execute(text("SET search_path TO ns, public;"))
                
                # Studies with activation at coords_a but not coords_b
                a_not_b_query = text("""
                    SELECT DISTINCT c1.study_id 
                    FROM ns.coordinates c1 
                    WHERE ST_DWithin(
                        c1.geom, 
                        ST_SetSRID(ST_MakePoint(:x1, :y1, :z1), 4326), 
                        :tolerance1
                    )
                    AND c1.study_id NOT IN (
                        SELECT study_id FROM ns.coordinates 
                        WHERE ST_DWithin(
                            geom, 
                            ST_SetSRID(ST_MakePoint(:x2, :y2, :z2), 4326), 
                            :tolerance2
                        )
                    )
                    ORDER BY c1.study_id
                """)
                
                # Studies with activation at coords_b but not coords_a
                b_not_a_query = text("""
                    SELECT DISTINCT c1.study_id 
                    FROM ns.coordinates c1 
                    WHERE ST_DWithin(
                        c1.geom, 
                        ST_SetSRID(ST_MakePoint(:x2, :y2, :z2), 4326), 
                        :tolerance1
                    )
                    AND c1.study_id NOT IN (
                        SELECT study_id FROM ns.coordinates 
                        WHERE ST_DWithin(
                            geom, 
                            ST_SetSRID(ST_MakePoint(:x1, :y1, :z1), 4326), 
                            :tolerance2
                        )
                    )
                    ORDER BY c1.study_id
                """)
                
                a_not_b_results = conn.execute(a_not_b_query, {
                    "x1": x1, "y1": y1, "z1": z1,
                    "x2": x2, "y2": y2, "z2": z2,
                    "tolerance1": tolerance, "tolerance2": tolerance
                }).fetchall()
                
                b_not_a_results = conn.execute(b_not_a_query, {
                    "x1": x1, "y1": y1, "z1": z1,
                    "x2": x2, "y2": y2, "z2": z2,
                    "tolerance1": tolerance, "tolerance2": tolerance
                }).fetchall()
                
                return jsonify({
                    "query": {
                        "coords_a": [x1, y1, z1],
                        "coords_b": [x2, y2, z2],
                        "tolerance_mm": tolerance
                    },
                    "results": {
                        f"coords_a_not_b": {
                            "coordinates": [x1, y1, z1],
                            "count": len(a_not_b_results),
                            "studies": [row[0] for row in a_not_b_results]
                        },
                        f"coords_b_not_a": {
                            "coordinates": [x2, y2, z2],
                            "count": len(b_not_a_results),
                            "studies": [row[0] for row in b_not_a_results]
                        }
                    }
                })
                
        except ValueError as e:
            return jsonify({"error": "Invalid coordinate format. Use x_y_z format (e.g., '0_-52_26')"}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.get("/test_db", endpoint="test_db")
    
    def test_db():
        eng = get_engine()
        payload = {"ok": False, "dialect": eng.dialect.name}

        try:
            with eng.begin() as conn:
                # Ensure we are in the correct schema
                conn.execute(text("SET search_path TO ns, public;"))
                payload["version"] = conn.exec_driver_sql("SELECT version()").scalar()

                # Counts
                payload["coordinates_count"] = conn.execute(text("SELECT COUNT(*) FROM ns.coordinates")).scalar()
                payload["metadata_count"] = conn.execute(text("SELECT COUNT(*) FROM ns.metadata")).scalar()
                payload["annotations_terms_count"] = conn.execute(text("SELECT COUNT(*) FROM ns.annotations_terms")).scalar()

                # Samples
                try:
                    rows = conn.execute(text(
                        "SELECT study_id, ST_X(geom) AS x, ST_Y(geom) AS y, ST_Z(geom) AS z FROM ns.coordinates LIMIT 3"
                    )).mappings().all()
                    payload["coordinates_sample"] = [dict(r) for r in rows]
                except Exception:
                    payload["coordinates_sample"] = []

                try:
                    # Select a few columns if they exist; otherwise select a generic subset
                    rows = conn.execute(text("SELECT * FROM ns.metadata LIMIT 3")).mappings().all()
                    payload["metadata_sample"] = [dict(r) for r in rows]
                except Exception:
                    payload["metadata_sample"] = []

                try:
                    rows = conn.execute(text(
                        "SELECT study_id, contrast_id, term, weight FROM ns.annotations_terms LIMIT 3"
                    )).mappings().all()
                    payload["annotations_terms_sample"] = [dict(r) for r in rows]
                except Exception:
                    payload["annotations_terms_sample"] = []

            payload["ok"] = True
            return jsonify(payload), 200

        except Exception as e:
            payload["error"] = str(e)
            return jsonify(payload), 500

    return app

# WSGI entry point (no __main__)
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
