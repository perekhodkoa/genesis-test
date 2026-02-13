from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=128)
    invite_code: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str


class InviteCodeResponse(BaseModel):
    code: str
    expires_at: str


class InviteCodeDetail(BaseModel):
    code: str
    created_at: str
    expires_at: str
    is_used: bool
    used_by: str | None = None
