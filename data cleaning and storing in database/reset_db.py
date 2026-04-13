"""Reset database: drop all tables and recreate them."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config.db_config import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("DROP TABLE IF EXISTS product_spec_values CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS product_numeric_specs CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS product_features CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS use_case_weights CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS spec_fields CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS spec_sections CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS products CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS brands CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS categories CASCADE"))
    conn.commit()
    print("All tables dropped.")