"""
Electronics Comparison Platform — Main Pipeline Orchestrator

Runs the full ETL pipeline:
1. Create database and tables
2. Load Excel files
3. Parse sections and fields
4. Insert products, specs, numeric data, and features
5. Seed use-case weights
6. Print summary statistics
"""
import os
import sys
import glob
import logging
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.db_config import create_database, create_tables, get_session
from pipeline.excel_loader import load_excel, get_spec_columns
from pipeline.section_parser import parse_columns
from pipeline.spec_inserter import process_excel_file
from pipeline.numeric_extractor import extract_numeric_specs
from pipeline.feature_extractor import extract_features
from pipeline.use_case_weights import insert_use_case_weights


def setup_logging():
    """Configure logging to both console and file."""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "pipeline.log")
    
    # Create formatters
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )
    
    # File handler
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return logging.getLogger(__name__)


def run_pipeline():
    """Run the full ETL pipeline."""
    logger = setup_logging()
    start_time = time.time()
    
    logger.info("=" * 60)
    logger.info("  Electronics Comparison Platform — ETL Pipeline")
    logger.info("=" * 60)
    
    # Step 1: Create database and tables
    logger.info("\n[Step 1] Creating database and tables...")
    create_database()
    create_tables()
    logger.info("  Database and tables ready.")
    
    # Step 2: Find all Excel files
    data_dir = os.path.dirname(os.path.abspath(__file__))
    excel_files = glob.glob(os.path.join(data_dir, "*.xlsx"))
    
    if not excel_files:
        logger.error("No Excel files found in the data directory!")
        return
    
    logger.info(f"\n[Step 2] Found {len(excel_files)} Excel file(s):")
    for f in excel_files:
        logger.info(f"  - {os.path.basename(f)}")
    
    # Step 3: Process each Excel file
    total_stats = {
        "files_processed": 0,
        "total_products": 0,
        "total_specs": 0,
        "total_numeric": 0,
        "total_features": 0,
        "total_errors": 0,
    }
    
    for filepath in excel_files:
        filename = os.path.basename(filepath)
        logger.info(f"\n{'='*50}")
        logger.info(f"[Step 3] Processing: {filename}")
        logger.info(f"{'='*50}")
        
        # Extract brand from filename: "apple_2000_2026.xlsx" → "Apple"
        brand_name = filename.split("_")[0].capitalize()
        logger.info(f"  Brand (from filename): {brand_name}")
        
        try:
            # Load and clean
            df = load_excel(filepath)
            spec_columns = get_spec_columns(df)
            logger.info(f"  Spec columns: {len(spec_columns)}")
            
            # Insert products and spec values
            session = get_session()
            try:
                stats = process_excel_file(
                    session, df, spec_columns, filename,
                    brand_override=brand_name
                )
                logger.info(f"  Products inserted: {stats['products_inserted']}")
                logger.info(f"  Spec values inserted: {stats['specs_inserted']}")
                
                if stats["errors"] > 0:
                    logger.warning(f"  Errors: {stats['errors']}")
                
                total_stats["total_products"] += stats["products_inserted"]
                total_stats["total_specs"] += stats["specs_inserted"]
                total_stats["total_errors"] += stats["errors"]
                
                # Step 4: Numeric extraction and feature extraction for each product
                logger.info(f"\n  [Step 4] Extracting numeric specs and features...")
                numeric_count = 0
                feature_count = 0
                
                from database.models import Product, Brand
                
                # Get the brand object once
                brand = session.query(Brand).filter_by(name=brand_name).first()
                if not brand:
                    logger.error(f"  Brand '{brand_name}' not found in DB!")
                    continue
                
                for _, row in df.iterrows():
                    product_name = str(row["phone_name"]).strip()
                    if not product_name:
                        continue
                    
                    product = session.query(Product).filter_by(
                        name=product_name, brand_id=brand.id
                    ).first()
                    if not product:
                        continue
                    
                    row_dict = row.to_dict()
                    
                    # Extract numeric specs (теперь включает price)
                    n = extract_numeric_specs(session, product.id, row_dict)
                    numeric_count += n
                    
                    # Extract features
                    f = extract_features(session, product.id, row_dict)
                    feature_count += f
                    
                    # Цена извлекается в numeric_extractor и сохраняется в product_numeric_specs,
                    # а также напрямую в поле product.price (см. изменения в numeric_extractor.py)
                
                session.commit()
                
                logger.info(f"  Numeric specs extracted: {numeric_count}")
                logger.info(f"  Features extracted: {feature_count}")
                
                total_stats["total_numeric"] += numeric_count
                total_stats["total_features"] += feature_count
                total_stats["files_processed"] += 1
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"  FATAL ERROR processing {filename}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            total_stats["total_errors"] += 1
    
    # Step 5: Insert use-case weights
    logger.info(f"\n[Step 5] Inserting use-case weight profiles...")
    session = get_session()
    try:
        insert_use_case_weights(session)
    finally:
        session.close()
    
    # Summary
    elapsed = time.time() - start_time
    logger.info(f"\n{'='*60}")
    logger.info(f"  PIPELINE COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"  Files processed:     {total_stats['files_processed']}")
    logger.info(f"  Total products:      {total_stats['total_products']}")
    logger.info(f"  Total spec values:   {total_stats['total_specs']}")
    logger.info(f"  Total numeric specs: {total_stats['total_numeric']}")
    logger.info(f"  Total features:      {total_stats['total_features']}")
    logger.info(f"  Errors:              {total_stats['total_errors']}")
    logger.info(f"  Time elapsed:        {elapsed:.2f}s")
    logger.info(f"{'='*60}")
    
    return total_stats


if __name__ == "__main__":
    run_pipeline()