from fastapi import FastAPI, HTTPException, Query, Depends
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import uvicorn

# ── Database Setup ────────────────────────────────────────────────────────────

DATABASE_URL = "sqlite:///./products.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class ProductModel(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)


Base.metadata.create_all(bind=engine)


# ── Dependency ────────────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=255, description="Name of the product")
    category: str = Field(..., min_length=1, max_length=100, description="Product category")
    price: float = Field(..., description="Price must be greater than 0")
    quantity: int = Field(..., description="Quantity must be greater than 0")

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Price must be greater than 0")
        return round(v, 2)

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Quantity must be greater than 0")
        return v


class ProductUpdate(BaseModel):
    product_name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    price: Optional[float] = None
    quantity: Optional[int] = None

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Price must be greater than 0")
        return round(v, 2) if v is not None else v

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Quantity must be greater than 0")
        return v


class ProductResponse(BaseModel):
    product_id: int
    product_name: str
    category: str
    price: float
    quantity: int

    model_config = {"from_attributes": True}


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Product Management API",
    description="REST API to manage products using FastAPI and SQLite",
    version="1.0.0",
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_product_or_404(product_id: int, db: Session) -> ProductModel:
    product = db.query(ProductModel).filter(ProductModel.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product with ID {product_id} not found")
    return product


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/products", response_model=ProductResponse, status_code=201, tags=["Products"])
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    """Create a new product."""
    new_product = ProductModel(**product.model_dump())
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product


@app.get("/products", response_model=list[ProductResponse], tags=["Products"])
def get_products(
    category: Optional[str] = Query(None, description="Filter products by category"),
    db: Session = Depends(get_db),
):
    """Get all products. Optionally filter by category using ?category=Electronics"""
    query = db.query(ProductModel)
    if category:
        query = query.filter(ProductModel.category.ilike(f"%{category}%"))
    return query.all()


@app.get("/products/{product_id}", response_model=ProductResponse, tags=["Products"])
def get_product(product_id: int, db: Session = Depends(get_db)):
    """Get a single product by ID."""
    return get_product_or_404(product_id, db)


@app.put("/products/{product_id}", response_model=ProductResponse, tags=["Products"])
def update_product(product_id: int, product_data: ProductUpdate, db: Session = Depends(get_db)):
    """Update an existing product (partial update supported)."""
    product = get_product_or_404(product_id, db)
    updates = product_data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    for field, value in updates.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@app.delete("/products/{product_id}", tags=["Products"])
def delete_product(product_id: int, db: Session = Depends(get_db)):
    """Delete a product by ID."""
    product = get_product_or_404(product_id, db)
    db.delete(product)
    db.commit()
    return {"message": f"Product with ID {product_id} has been deleted successfully"}


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
