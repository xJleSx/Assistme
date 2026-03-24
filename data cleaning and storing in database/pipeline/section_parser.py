"""
Section and field parser — parses SECTION_FIELD column names, detects category and brand.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Multi-word sections: column prefixes that map to multi-word section names
MULTI_WORD_SECTIONS = {
    "MAIN_CAMERA": "MAIN CAMERA",
    "SELFIE_CAMERA": "SELFIE CAMERA",
    "OUR_TESTS": "OUR TESTS",
    "EU_LABEL": "EU LABEL",
}

# Display name overrides for fields that need special rendering
DISPLAY_NAME_OVERRIDES = {
    "35mm_jack": "3.5mm jack",
    "2G_bands": "2G bands",
    "3G_bands": "3G bands",
    "4G_bands": "4G bands",
    "5G_bands": "5G bands",
}


def detect_category(product_name: str) -> str:
    """
    Detect device category from product name.
    
    Rules:
        if "watch" in name → watch
        if "tab" or "pad" in name → tablet
        else → mobile
    """
    name_lower = product_name.lower()
    if "watch" in name_lower:
        return "watch"
    if "tab" in name_lower or "pad" in name_lower:
        return "tablet"
    return "mobile"


def detect_brand(product_name: str) -> str:
    """
    Extract brand from product name (first word).
    
    Example:
        Apple iPhone 16 → Apple
        Samsung Galaxy S24 → Samsung
    """
    parts = product_name.strip().split()
    if parts:
        return parts[0]
    return "Unknown"


def _generate_display_name(raw_field: str) -> str:
    """
    Generate a human-readable display name from a raw field name.
    
    Rules:
        - Check overrides first
        - Replace underscores with spaces
        - Keep first letter casing as-is
    
    Examples:
        Card_slot → Card slot
        Talk_time → Talk time
        Infrared_port → Infrared port
    """
    if raw_field in DISPLAY_NAME_OVERRIDES:
        return DISPLAY_NAME_OVERRIDES[raw_field]
    return raw_field.replace("_", " ")


def parse_column(column_name: str) -> tuple:
    """
    Parse a single SECTION_FIELD column name into (section, field, display_name).
    
    Handles multi-word sections like MAIN_CAMERA, SELFIE_CAMERA, etc.
    Handles bare section columns like BODY_ → (BODY, General, General)
    
    Returns:
        (section_name, field_name, display_name)
    """
    # Check for multi-word section prefixes first
    for prefix, section_name in MULTI_WORD_SECTIONS.items():
        if column_name.startswith(prefix + "_"):
            remainder = column_name[len(prefix) + 1:]
            if remainder == "" or remainder is None:
                return (section_name, "General", "General")
            return (section_name, remainder, _generate_display_name(remainder))
        elif column_name == prefix:
            return (section_name, "General", "General")
    
    # Handle single-word sections
    # Find the first underscore
    idx = column_name.find("_")
    if idx == -1:
        # No underscore — treat entire thing as section with General field
        return (column_name, "General", "General")
    
    section = column_name[:idx]
    field = column_name[idx + 1:]
    
    if field == "" or field is None:
        field = "General"
        display_name = "General"
    else:
        display_name = _generate_display_name(field)
    
    return (section, field, display_name)


def parse_columns(columns: list) -> list:
    """
    Parse a list of SECTION_FIELD columns into structured tuples.
    Preserves Excel column order via display_order.
    
    Returns:
        list of (section, field, display_name, display_order)
    """
    result = []
    order = 0
    for col in columns:
        section, field, display_name = parse_column(col)
        result.append((section, field, display_name, order))
        order += 1
    return result


def make_slug(name: str) -> str:
    """
    Generate a URL-friendly slug from a name.
    
    Example:
        Apple iPhone 16 Pro Max → apple-iphone-16-pro-max
    """
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")
