import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from datetime import datetime
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import User as UserSchema, Service as ServiceSchema, Payment as PaymentSchema, Result as ResultSchema

app = FastAPI(title="Laboratory API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility to convert ObjectId

def to_str_id(doc: dict):
    if doc is None:
        return None
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    # datetime to iso
    for k, v in list(doc.items()):
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
    return doc

# Auth models
class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    token: str
    name: str
    email: EmailStr

# NOTE: For demo we store password hash and use a simple token (not prod). In real apps use JWT + proper hashing.
from hashlib import sha256

def hash_password(p: str) -> str:
    return sha256(p.encode()).hexdigest()

@app.get("/")
def read_root():
    return {"message": "Laboratory API running"}

# Auth endpoints
@app.post("/auth/signup", response_model=AuthResponse)
def signup(payload: SignupRequest):
    # check exists
    exists = db["user"].find_one({"email": payload.email}) if db else None
    if exists:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = UserSchema(name=payload.name, email=payload.email, password_hash=hash_password(payload.password))
    user_id = create_document("user", user)
    # Simple token: hash of email + created id
    token = sha256(f"{payload.email}:{user_id}".encode()).hexdigest()
    return AuthResponse(token=token, name=payload.name, email=payload.email)

@app.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    user = db["user"].find_one({"email": payload.email}) if db else None
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.get("password_hash") != hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = sha256(f"{user['email']}:{str(user['_id'])}".encode()).hexdigest()
    return AuthResponse(token=token, name=user["name"], email=user["email"]) 

# Services endpoints
@app.get("/services", response_model=List[dict])
def list_services():
    items = get_documents("service")
    return [to_str_id(x) for x in items]

class CreateService(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    price: float

@app.post("/services", response_model=dict)
def create_service(payload: CreateService):
    # enforce unique code
    if db["service"].find_one({"code": payload.code}):
        raise HTTPException(status_code=400, detail="Service code already exists")
    service = ServiceSchema(code=payload.code, name=payload.name, description=payload.description, price=payload.price)
    new_id = create_document("service", service)
    created = db["service"].find_one({"_id": ObjectId(new_id)})
    return to_str_id(created)

# Payment endpoints (simple demo, marks as paid)
class CreatePayment(BaseModel):
    user_email: EmailStr
    service_code: str

@app.post("/payments", response_model=dict)
def create_payment(payload: CreatePayment):
    user = db["user"].find_one({"email": payload.user_email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    service = db["service"].find_one({"code": payload.service_code})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    amount = float(service["price"])
    payment = PaymentSchema(
        user_id=str(user["_id"]),
        service_code=service["code"],
        amount=amount,
        status="paid",
        reference=sha256(f"{user['_id']}:{service['code']}:{datetime.utcnow().isoformat()}".encode()).hexdigest()[:12]
    )
    pay_id = create_document("payment", payment)
    created = db["payment"].find_one({"_id": ObjectId(pay_id)})
    return to_str_id(created)

# Results endpoints
@app.get("/results", response_model=List[dict])
def list_results(user_email: Optional[str] = None):
    filt = {}
    if user_email:
        u = db["user"].find_one({"email": user_email})
        if not u:
            return []
        filt = {"user_id": str(u["_id"]) }
    items = get_documents("result", filt)
    return [to_str_id(x) for x in items]

class CreateResult(BaseModel):
    user_email: EmailStr
    service_code: str
    values: dict
    notes: Optional[str] = None

@app.post("/results", response_model=dict)
def create_result(payload: CreateResult):
    user = db["user"].find_one({"email": payload.user_email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not db["service"].find_one({"code": payload.service_code}):
        raise HTTPException(status_code=404, detail="Service not found")
    result = ResultSchema(
        user_id=str(user["_id"]),
        service_code=payload.service_code,
        values=payload.values,
        notes=payload.notes
    )
    res_id = create_document("result", result)
    created = db["result"].find_one({"_id": ObjectId(res_id)})
    return to_str_id(created)

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
