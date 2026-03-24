"""
Excel file loader — reads and cleans Excel files for the pipeline.
"""
import os
import logging
import pandas as pd

logger = logging.getLogger(__name__)

# Known non-spec columns that appear in all files
NON_SPEC_COLUMNS = {"phone_name", "announced_date", "url", "scraped_at"}


def load_excel(filepath: str) -> pd.DataFrame:
    """
    Load an Excel file and return a cleaned DataFrame.
    
    - Drops rows where phone_name is null
    - Strips whitespace from column names
    - Strips whitespace from string values
    """
    filename = os.path.basename(filepath)
    logger.info(f"Loading Excel file: {filename}")
    
    df = pd.read_excel(filepath)
    original_count = len(df)
    
    # Strip column names
    df.columns = [col.strip() for col in df.columns]
    
    # Drop rows with no product name
    df = df.dropna(subset=["phone_name"])
    df = df[df["phone_name"].str.strip() != ""]
    
    cleaned_count = len(df)
    dropped = original_count - cleaned_count
    if dropped > 0:
        logger.info(f"  Dropped {dropped} empty rows from {filename}")
    
    logger.info(f"  Loaded {cleaned_count} products from {filename}")
    return df


def get_spec_columns(df: pd.DataFrame) -> list:
    """
    Return the list of spec columns (those matching SECTION_FIELD pattern).
    Preserves the original column order from the Excel file.
    """
    spec_cols = []
    for col in df.columns:
        if col.lower() not in {c.lower() for c in NON_SPEC_COLUMNS}:
            # Must contain at least one underscore to be a spec column
            if "_" in col:
                spec_cols.append(col)
    return spec_cols
