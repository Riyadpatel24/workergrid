from pydantic import BaseModel, EmailStr, Field


class UserSignup(BaseModel):
    email: EmailStr = Field(..., example="user@example.com")
    password: str = Field(..., min_length=8, example="securepassword123")
    full_name: str | None = Field(default=None, example="Jane Developer")


class UserLogin(BaseModel):
    email: EmailStr = Field(..., example="user@example.com")
    password: str = Field(..., example="securepassword123")


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    is_active: bool = True
    has_github_connected: bool = False
    github_username: str | None = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class OAuthLoginResponse(BaseModel):
    authorization_url: str
    state: str
