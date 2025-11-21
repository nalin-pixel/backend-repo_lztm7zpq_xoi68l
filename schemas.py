"""
Database Schemas for Laboratory App

Each Pydantic model represents a collection in MongoDB.
Collection name is the lowercase of the class name.
"""
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

class User(BaseModel):
    """
    Users collection schema
    Collection: "user"
    """
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    password_hash: str = Field(..., description="BCrypt hash of the user's password")
    role: str = Field("patient", description="Role of the user (patient/admin)")
    is_active: bool = Field(True, description="Whether user is active")

class Service(BaseModel):
    """
    Laboratory services/tests offered
    Collection: "service"
    """
    code: str = Field(..., description="Unique service code, e.g. CBC")
    name: str = Field(..., description="Service name")
    description: Optional[str] = Field(None, description="Short description")
    price: float = Field(..., ge=0, description="Price in USD")
    active: bool = Field(True, description="Whether this service is available")

class Payment(BaseModel):
    """
    Payment/Order record
    Collection: "payment"
    """
    user_id: str = Field(..., description="User identifier (as string)")
    service_code: str = Field(..., description="Purchased service code")
    amount: float = Field(..., ge=0, description="Charged amount")
    status: str = Field("paid", description="Payment status: pending/paid/failed/refunded")
    reference: str = Field(..., description="Gateway reference or internal ref")

class Result(BaseModel):
    """
    Test results for a user
    Collection: "result"
    """
    user_id: str = Field(..., description="User identifier (as string)")
    service_code: str = Field(..., description="Related service/test code")
    values: dict = Field(default_factory=dict, description="Result values as key-value pairs")
    notes: Optional[str] = Field(None, description="Additional notes")
    reported_at: datetime = Field(default_factory=datetime.utcnow, description="Report timestamp")
