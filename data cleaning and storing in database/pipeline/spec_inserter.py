"""
Spec inserter — inserts categories, brands, products, sections, fields, and spec values.
"""
import logging
import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert
from database.models import (
    Category, Brand, Product, SpecSection, SpecField, ProductSpecValue
)
from pipeline.section_parser import detect_category, detect_brand, make_slug, parse_columns

logger = logging.getLogger(__name__)


def ensure_category(session, name: str) -> Category:
    """Get or create a category."""
    slug = name.lower().strip()
    cat = session.query(Category).filter_by(name=name).first()
    if not cat:
        cat = Category(name=name, slug=slug)
        session.add(cat)
        session.flush()
        logger.debug(f"  Created category: {name}")
    return cat


def ensure_brand(session, name: str) -> Brand:
    """Get or create a brand."""
    brand = session.query(Brand).filter_by(name=name).first()
    if not brand:
        brand = Brand(name=name)
        session.add(brand)
        session.flush()
        logger.debug(f"  Created brand: {name}")
    return brand


def insert_product(session, name: str, brand_id: int, category_id: int,
                   release_date=None, model_code=None, url=None) -> Product:
    """Insert a product, skip if duplicate (same name + brand)."""
    existing = session.query(Product).filter_by(name=name, brand_id=brand_id).first()
    if existing:
        logger.debug(f"  Product already exists: {name}")
        return existing
    
    product = Product(
        name=name,
        slug=make_slug(name),
        model_code=model_code,
        url=url,
        brand_id=brand_id,
        category_id=category_id,
        release_date=release_date,
    )
    session.add(product)
    session.flush()
    return product


def insert_sections_and_fields(session, category_id: int, parsed_columns: list) -> dict:
    """
    Insert spec sections and fields for a category.
    
    Args:
        parsed_columns: list of (section, field, display_name, display_order)
    
    Returns:
        field_map: dict mapping original_column_key -> field_id
    """
    field_map = {}
    section_cache = {}
    section_order = 0
    
    for section_name, field_name, display_name, col_order in parsed_columns:
        # Get or create section
        if section_name not in section_cache:
            sec = session.query(SpecSection).filter_by(
                category_id=category_id, name=section_name
            ).first()
            if not sec:
                sec = SpecSection(
                    category_id=category_id,
                    name=section_name,
                    display_order=section_order
                )
                session.add(sec)
                session.flush()
                section_order += 1
            section_cache[section_name] = sec
        
        section = section_cache[section_name]
        
        # Get or create field
        fld = session.query(SpecField).filter_by(
            section_id=section.id, name=field_name
        ).first()
        if not fld:
            fld = SpecField(
                section_id=section.id,
                name=field_name,
                display_name=display_name,
                display_order=col_order
            )
            session.add(fld)
            session.flush()
        
        # Map: (section_name, field_name) -> field_id
        field_map[(section_name, field_name)] = fld.id
    
    return field_map


def insert_spec_values(session, product_id: int, field_map: dict,
                       row_data: dict, parsed_columns: list):
    """
    Insert spec values for a product.
    
    Args:
        field_map: dict mapping (section, field) -> field_id
        row_data: dict of column_name -> value from the DataFrame row
        parsed_columns: list of (section, field, display_name, order)
    """
    values_to_insert = []
    
    for section_name, field_name, display_name, col_order in parsed_columns:
        key = (section_name, field_name)
        if key not in field_map:
            continue
        
        field_id = field_map[key]
        
        # Reconstruct the original column name to look up the value
        # We need to find the matching column in the row data
        value = _find_value_for_field(row_data, section_name, field_name, parsed_columns)
        
        if value is not None and str(value).strip() != "" and str(value).lower() != "nan":
            values_to_insert.append({
                "product_id": product_id,
                "field_id": field_id,
                "value": str(value).strip()
            })
    
    if values_to_insert:
        stmt = pg_insert(ProductSpecValue).values(values_to_insert)
        stmt = stmt.on_conflict_do_nothing(index_elements=["product_id", "field_id"])
        session.execute(stmt)
    
    return len(values_to_insert)


def _find_value_for_field(row_data: dict, section_name: str, field_name: str,
                          parsed_columns: list):
    """
    Find the value in row_data that corresponds to a parsed (section, field).
    
    We need to reverse-map from parsed names back to the original column name.
    """
    # Try direct reconstruction
    # For multi-word sections, we need to reconstruct the original column name
    section_key = section_name.replace(" ", "_")
    
    if field_name == "General":
        # Bare column like BODY_
        col_name = section_key + "_"
        if col_name in row_data:
            return row_data[col_name]
        # Also try without trailing underscore
        if section_key in row_data:
            return row_data[section_key]
    else:
        col_name = section_key + "_" + field_name
        if col_name in row_data:
            return row_data[col_name]
    
    return None


def process_excel_file(session, df: pd.DataFrame, spec_columns: list,
                       filename: str, brand_override: str = None) -> dict:
    """
    Process an entire Excel DataFrame: insert all categories, brands, products,
    sections, fields, and spec values.
    
    Args:
        brand_override: If provided, use this as the brand name instead of
                       detecting from product name. This is needed when the
                       product names don't include the brand prefix
                       (e.g. Oppo files have "Reno15 Pro" not "Oppo Reno15 Pro").
    
    Returns:
        dict with processing statistics
    """
    stats = {
        "products_inserted": 0,
        "products_skipped": 0,
        "specs_inserted": 0,
        "errors": 0,
    }
    
    # Parse spec columns
    parsed_columns = parse_columns(spec_columns)
    
    # Cache for categories and brands per file
    category_cache = {}
    brand_cache = {}
    field_map_cache = {}
    
    for idx, row in df.iterrows():
        try:
            product_name = str(row["phone_name"]).strip()
            if not product_name:
                continue
            
            # Detect category and brand
            cat_name = detect_category(product_name)
            brand_name = brand_override if brand_override else detect_brand(product_name)
            
            # Ensure category
            if cat_name not in category_cache:
                category_cache[cat_name] = ensure_category(session, cat_name)
            category = category_cache[cat_name]
            
            # Ensure brand
            if brand_name not in brand_cache:
                brand_cache[brand_name] = ensure_brand(session, brand_name)
            brand = brand_cache[brand_name]
            
            # Insert sections and fields (once per category per file)
            if category.id not in field_map_cache:
                field_map_cache[category.id] = insert_sections_and_fields(
                    session, category.id, parsed_columns
                )
            field_map = field_map_cache[category.id]
            
            # Get model code and URL
            model_code = None
            if "MISC_Models" in row.index:
                val = row["MISC_Models"]
                if pd.notna(val) and str(val).strip():
                    model_code = str(val).strip()
            
            url = None
            if "url" in row.index:
                val = row["url"]
                if pd.notna(val) and str(val).strip():
                    url = str(val).strip()
            
            release_date = None
            if "announced_date" in row.index:
                val = row["announced_date"]
                if pd.notna(val) and str(val).strip():
                    release_date = str(val).strip()
            
            # Insert product
            product = insert_product(
                session, product_name, brand.id, category.id,
                release_date=release_date, model_code=model_code, url=url
            )
            
            if product.id:
                stats["products_inserted"] += 1
            
            # Insert spec values
            row_dict = row.to_dict()
            count = insert_spec_values(
                session, product.id, field_map, row_dict, parsed_columns
            )
            stats["specs_inserted"] += count
            
        except Exception as e:
            stats["errors"] += 1
            logger.error(f"  Error processing product '{product_name}': {e}")
            continue
    
    session.commit()
    return stats
