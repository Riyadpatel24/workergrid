import json
import os
import urllib.error
import urllib.parse
import urllib.request
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.auth_schemas import (
    OAuthLoginResponse,
    TokenResponse,
    UserLogin,
    UserResponse,
    UserSignup,
)
from app.api.deps import get_current_user, get_optional_current_user
from app.core.security import (
    create_access_token,
    create_oauth_state,
    create_refresh_token,
    decode_token,
    encrypt_token,
    get_password_hash,
    verify_oauth_state,
    verify_password,
)
from app.db.dependencies import get_db
from app.models.user import User, UserGitHubAccount

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & GitHub OAuth"])

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "mock_github_client_id")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "mock_github_client_secret")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/api/v1/auth/github/callback")
# Minimum GitHub OAuth scopes required by Project Friction (repo for private repos, read:user for user profile)
GITHUB_SCOPES = os.getenv("GITHUB_OAUTH_SCOPES", "repo,read:user")


def format_user_response(user: User) -> UserResponse:
    has_gh = user.github_account is not None
    gh_username = user.github_account.github_username if has_gh else None
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        has_github_connected=has_gh,
        github_username=gh_username,
    )


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=1800,  # 30 mins
        samesite="lax",
        secure=os.getenv("ENVIRONMENT") == "production",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=604800,  # 7 days
        samesite="lax",
        secure=os.getenv("ENVIRONMENT") == "production",
    )


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(req: UserSignup, response: Response, db: Session = Depends(get_db)):
    email_clean = req.email.strip().lower()
    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")

    hashed_pwd = get_password_hash(req.password)
    user = User(
        email=email_clean,
        hashed_password=hashed_pwd,
        full_name=req.full_name.strip() if req.full_name else None,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=format_user_response(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(req: UserLogin, response: Response, db: Session = Depends(get_db)):
    email_clean = req.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()
    if not user or not user.hashed_password or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=format_user_response(user),
    )


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return format_user_response(current_user)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")

    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(err))

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    new_access_token = create_access_token({"sub": str(user.id)})
    new_refresh_token = create_refresh_token({"sub": str(user.id)})
    set_auth_cookies(response, new_access_token, new_refresh_token)

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        user=format_user_response(user),
    )


@router.get("/github/login", response_model=OAuthLoginResponse)
def github_login(current_user: User | None = Depends(get_optional_current_user)):
    user_id = current_user.id if current_user else None
    state = create_oauth_state(user_id=user_id)

    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": GITHUB_SCOPES,
        "state": state,
    }
    url = f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"
    return OAuthLoginResponse(authorization_url=url, state=state)


@router.get("/github/callback", response_model=TokenResponse)
def github_callback(
    code: str = Query(...),
    state: str = Query(...),
    response: Response = None,
    db: Session = Depends(get_db),
):
    # 1. CSRF State Validation
    try:
        state_payload = verify_oauth_state(state)
        bound_user_id = state_payload.get("user_id")
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"OAuth state CSRF validation failed: {err}")

    # 2. Exchange authorization code for access token
    token_url = "https://github.com/login/oauth/access_token"
    token_params = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": GITHUB_REDIRECT_URI,
    }
    headers = {"Accept": "application/json", "User-Agent": "WorkerGrid-OAuth/1.0"}

    try:
        req_data = urllib.parse.urlencode(token_params).encode("utf-8")
        req = urllib.request.Request(token_url, data=req_data, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to exchange code with GitHub: {err}")

    access_token = token_data.get("access_token")
    if not access_token:
        error_desc = token_data.get("error_description", token_data.get("error", "OAuth token exchange failed"))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"GitHub OAuth error: {error_desc}")

    # 3. Retrieve GitHub user identity
    try:
        user_req = urllib.request.Request(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "User-Agent": "WorkerGrid-OAuth/1.0", "Accept": "application/vnd.github.v3+json"},
        )
        with urllib.request.urlopen(user_req, timeout=10) as resp:
            gh_user = json.loads(resp.read().decode("utf-8"))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to fetch GitHub user profile: {err}")

    gh_user_id = gh_user.get("id")
    gh_username = gh_user.get("login")
    gh_email = gh_user.get("email")

    if not gh_user_id or not gh_username:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid GitHub profile payload")

    # 4. Resolve WorkerGrid User account
    user = None
    if bound_user_id:
        user = db.query(User).filter(User.id == int(bound_user_id)).first()

    if not user and gh_email:
        user = db.query(User).filter(User.email == gh_email.lower()).first()

    # Check if this GitHub account is already linked to another user
    existing_gh_account = db.query(UserGitHubAccount).filter(UserGitHubAccount.github_user_id == gh_user_id).first()
    if existing_gh_account:
        if user and existing_gh_account.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This GitHub account is already linked to a different WorkerGrid user")
        user = existing_gh_account.user

    if not user:
        # Auto-create User account for new GitHub OAuth user
        email_val = (gh_email or f"{gh_username}@github.user").lower()
        user = User(
            email=email_val,
            full_name=gh_user.get("name") or gh_username,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # 5. Encrypt token before storing (NEVER store plain-text token or return to frontend JS)
    encrypted_token = encrypt_token(access_token)
    scopes_str = token_data.get("scope", GITHUB_SCOPES)

    gh_account = db.query(UserGitHubAccount).filter(UserGitHubAccount.user_id == user.id).first()
    if not gh_account:
        gh_account = UserGitHubAccount(
            user_id=user.id,
            github_user_id=gh_user_id,
            github_username=gh_username,
            encrypted_access_token=encrypted_token,
            scopes=scopes_str,
        )
        db.add(gh_account)
    else:
        gh_account.github_user_id = gh_user_id
        gh_account.github_username = gh_username
        gh_account.encrypted_access_token = encrypted_token
        gh_account.scopes = scopes_str

    db.commit()
    db.refresh(user)

    access_jwt = create_access_token({"sub": str(user.id)})
    refresh_jwt = create_refresh_token({"sub": str(user.id)})
    set_auth_cookies(response, access_jwt, refresh_jwt)

    return TokenResponse(
        access_token=access_jwt,
        token_type="bearer",
        user=format_user_response(user),
    )


@router.post("/github/disconnect")
def github_disconnect(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = db.query(UserGitHubAccount).filter(UserGitHubAccount.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No connected GitHub account found")

    db.delete(account)
    db.commit()
    return {"message": "GitHub account disconnected successfully"}
