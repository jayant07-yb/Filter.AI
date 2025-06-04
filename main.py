from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Dict, Optional
import jwt
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer, util
import uuid

# === Config ===
SECRET_KEY = "your-super-secret-key"  # change for prod
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

USER_DATA = {"username": "admin", "password": "adminpass"}

app = FastAPI()
security = HTTPBearer()

# Global model loaded once
model = None

# In-memory store of schema extractors
schemas_store: Dict[str, "FlexibleSearchFilterExtractor"] = {}

# ==== Models ====

class TokenRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class RegisterFilterRequest(BaseModel):
    filters: Dict[str, Dict[str, str]]  # filter type -> option -> description
    threshold: Optional[float] = 0.45

class RegisterFilterResponse(BaseModel):
    schema_id: str

class QueryTextRequest(BaseModel):
    schema_id: str
    query: str

class QueryTextResponse(BaseModel):
    filters: Dict[str, str]

# ==== JWT utils ====

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username != USER_DATA["username"]:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    return verify_token(token)

# ==== Filter Extractor ====

class FlexibleSearchFilterExtractor:
    def __init__(self, model: SentenceTransformer, candidate_filters: Dict[str, Dict[str, str]], threshold: float = 0.54):
        self.model = model
        self.threshold = threshold
        self.candidate_filters = candidate_filters

    def extract_filters(self, query: str):
        query_emb = self.model.encode(query, convert_to_tensor=True)
        filters = {}
        for ftype, options in self.candidate_filters.items():
            descriptions = list(options.values())
            keys = list(options.keys())
            emb_options = self.model.encode(descriptions, convert_to_tensor=True)
            scores = util.cos_sim(query_emb, emb_options)[0]
            best_idx = int(scores.argmax())
            if float(scores[best_idx]) >= self.threshold:
                filters[ftype] = keys[best_idx]
        return filters

# ==== App lifecycle events ====

@app.on_event("startup")
async def startup_event():
    global model
    print("Loading model 'BAAI/bge-large-en-v1.5' ...")
    model = SentenceTransformer('BAAI/bge-large-en-v1.5')
    print("Model loaded.")

# ==== API Endpoints ====

@app.post("/get_token", response_model=TokenResponse)
def get_token(req: TokenRequest):
    if req.username != USER_DATA["username"] or req.password != USER_DATA["password"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    access_token = create_access_token(data={"sub": req.username})
    return {"access_token": access_token}

@app.post("/register_filter", response_model=RegisterFilterResponse)
async def register_filter(
    req: RegisterFilterRequest,
    username: str = Depends(get_current_user)
):
    global model
    if model is None:
        raise HTTPException(status_code=500, detail="Model not loaded yet")

    schema_id = str(uuid.uuid4())
    extractor = FlexibleSearchFilterExtractor(model=model, candidate_filters=req.filters, threshold=req.threshold or 0.45)
    schemas_store[schema_id] = extractor
    return {"schema_id": schema_id}

@app.post("/query_text", response_model=QueryTextResponse)
async def query_text(req: QueryTextRequest):
    extractor = schemas_store.get(req.schema_id)
    if not extractor:
        raise HTTPException(status_code=404, detail="Schema ID not found")
    filters = extractor.extract_filters(req.query)
    return {"filters": filters}
