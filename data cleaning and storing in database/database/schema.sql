-- ============================================================
-- Electronics Comparison Platform — Database Schema
-- ============================================================

-- 1. Categories
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2. Brands
CREATE TABLE IF NOT EXISTS brands (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    logo_url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 3. Products
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    slug VARCHAR(500) NOT NULL,
    model_code TEXT,
    url TEXT,
    brand_id INTEGER REFERENCES brands(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
    release_date VARCHAR(200),
    image_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(name, brand_id)
);

CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_slug ON products(slug);

-- 4. Spec Sections
CREATE TABLE IF NOT EXISTS spec_sections (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    display_order INTEGER DEFAULT 0,
    UNIQUE(category_id, name)
);

CREATE INDEX IF NOT EXISTS idx_spec_sections_category ON spec_sections(category_id);

-- 5. Spec Fields
CREATE TABLE IF NOT EXISTS spec_fields (
    id SERIAL PRIMARY KEY,
    section_id INTEGER REFERENCES spec_sections(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    display_name VARCHAR(300),
    display_order INTEGER DEFAULT 0,
    UNIQUE(section_id, name)
);

CREATE INDEX IF NOT EXISTS idx_spec_fields_section ON spec_fields(section_id);

-- 6. Product Spec Values
CREATE TABLE IF NOT EXISTS product_spec_values (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    field_id INTEGER REFERENCES spec_fields(id) ON DELETE CASCADE,
    value TEXT,
    UNIQUE(product_id, field_id)
);

CREATE INDEX IF NOT EXISTS idx_spec_values_product ON product_spec_values(product_id);
CREATE INDEX IF NOT EXISTS idx_spec_values_field ON product_spec_values(field_id);

-- 7. Product Numeric Specs
CREATE TABLE IF NOT EXISTS product_numeric_specs (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    spec_key VARCHAR(200) NOT NULL,
    numeric_value DOUBLE PRECISION,
    UNIQUE(product_id, spec_key)
);

CREATE INDEX IF NOT EXISTS idx_numeric_specs_product ON product_numeric_specs(product_id);
CREATE INDEX IF NOT EXISTS idx_numeric_specs_key_val ON product_numeric_specs(spec_key, numeric_value);

-- 8. Product Features
CREATE TABLE IF NOT EXISTS product_features (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    feature_key VARCHAR(200) NOT NULL,
    feature_value_numeric DOUBLE PRECISION,
    feature_value_text TEXT,
    UNIQUE(product_id, feature_key)
);

CREATE INDEX IF NOT EXISTS idx_features_product ON product_features(product_id);
CREATE INDEX IF NOT EXISTS idx_features_key ON product_features(feature_key);

-- 9. Use Case Weights
CREATE TABLE IF NOT EXISTS use_case_weights (
    id SERIAL PRIMARY KEY,
    use_case VARCHAR(200) NOT NULL,
    feature_key VARCHAR(200) NOT NULL,
    weight DOUBLE PRECISION NOT NULL,
    UNIQUE(use_case, feature_key)
);
