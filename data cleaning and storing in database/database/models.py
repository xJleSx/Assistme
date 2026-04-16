"""
SQLAlchemy ORM models for the Electronics Comparison Platform.
"""
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    products = relationship("Product", back_populates="category")
    spec_sections = relationship("SpecSection", back_populates="category")

    def __repr__(self):
        return f"<Category(name='{self.name}')>"


class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), unique=True, nullable=False)
    logo_url = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    products = relationship("Product", back_populates="brand")

    def __repr__(self):
        return f"<Brand(name='{self.name}')>"


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(500), nullable=False)
    slug = Column(String(500), nullable=False)
    model_code = Column(Text)
    url = Column(Text)
    brand_id = Column(Integer, ForeignKey("brands.id", ondelete="CASCADE"))
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"))
    release_date = Column(String(200))
    image_url = Column(Text)
    price = Column(Float)
    price_currency = Column(String(3))      # <-- валюта
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("name", "brand_id"),)

    brand = relationship("Brand", back_populates="products")
    category = relationship("Category", back_populates="products")
    spec_values = relationship("ProductSpecValue", back_populates="product", cascade="all, delete-orphan")
    features = relationship("ProductFeature", back_populates="product", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Product(name='{self.name}')>"


class SpecSection(Base):
    __tablename__ = "spec_sections"

    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"))
    name = Column(String(200), nullable=False)
    display_order = Column(Integer, default=0)

    __table_args__ = (UniqueConstraint("category_id", "name"),)

    category = relationship("Category", back_populates="spec_sections")
    fields = relationship("SpecField", back_populates="section", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SpecSection(name='{self.name}')>"


class SpecField(Base):
    __tablename__ = "spec_fields"

    id = Column(Integer, primary_key=True)
    section_id = Column(Integer, ForeignKey("spec_sections.id", ondelete="CASCADE"))
    name = Column(String(200), nullable=False)
    display_name = Column(String(300))
    display_order = Column(Integer, default=0)

    __table_args__ = (UniqueConstraint("section_id", "name"),)

    section = relationship("SpecSection", back_populates="fields")
    spec_values = relationship("ProductSpecValue", back_populates="field")

    def __repr__(self):
        return f"<SpecField(name='{self.name}')>"


class ProductSpecValue(Base):
    __tablename__ = "product_spec_values"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"))
    field_id = Column(Integer, ForeignKey("spec_fields.id", ondelete="CASCADE"))
    value = Column(Text)

    __table_args__ = (UniqueConstraint("product_id", "field_id"),)

    product = relationship("Product", back_populates="spec_values")
    field = relationship("SpecField", back_populates="spec_values")


class ProductFeature(Base):
    __tablename__ = "product_features"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"))
    feature_key = Column(String(200), nullable=False)
    feature_value_numeric = Column(Float)
    feature_value_text = Column(Text)

    __table_args__ = (UniqueConstraint("product_id", "feature_key"),)

    product = relationship("Product", back_populates="features")


class UseCaseWeight(Base):
    __tablename__ = "use_case_weights"

    id = Column(Integer, primary_key=True)
    use_case = Column(String(200), nullable=False)
    feature_key = Column(String(200), nullable=False)
    weight = Column(Float, nullable=False)

    __table_args__ = (UniqueConstraint("use_case", "feature_key"),)