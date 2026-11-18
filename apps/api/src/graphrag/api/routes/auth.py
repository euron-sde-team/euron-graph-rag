"""Sign-in, sign-up, the current user, password and profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from graphrag.api.deps import ContainerDep, PrincipalDep, SessionDep, UserDep, client_ip
from graphrag.core.errors import RateLimitedError, ServiceUnavailableError
from graphrag.core.security import SessionClaims
from graphrag.models import User
from graphrag.schemas.auth import (
    LoginRequest,
    MeOut,
    PasswordChange,
    ProfileUpdate,
    ProjectSummaryOut,
    SessionOut,
    SignupRequest,
    UserOut,
)
from graphrag.services.auth import SESSION_COOKIE, AuthService
from graphrag.services.container import Container
from graphrag.services.principal import Principal
from graphrag.services.projects import ProjectService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _set_cookie(
    response: Response, container: Container, token: str, claims: SessionClaims
) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=container.settings.session_ttl_hours * 3600,
        httponly=True,
        secure=container.settings.cookie_secure,
        samesite="lax",
        domain=container.settings.cookie_domain,
        path="/",
    )


async def _login_rate_limit(request: Request, response: Response, container: ContainerDep) -> None:
    try:
        result = await container.limiter.hit(
            f"login:{client_ip(request)}", container.settings.rate_limit_login
        )
    except Exception as exc:
        # Without the counter, password guessing would be unthrottled: refuse instead.
        raise ServiceUnavailableError(
            "Sign-in is unavailable for a moment. Try again shortly."
        ) from exc
    response.headers.update(result.headers())
    if not result.allowed:
        raise RateLimitedError("Too many sign-in attempts. Wait a minute and try again.")


@router.post("/login", summary="Sign in", dependencies=[Depends(_login_rate_limit)])
async def login(
    body: LoginRequest, response: Response, container: ContainerDep, session: SessionDep
) -> SessionOut:
    user, token, claims = await AuthService(container, session).login(body.email, body.password)
    _set_cookie(response, container, token, claims)
    return SessionOut(user=UserOut.model_validate(user), token=token, expires_at=claims.expires_at)


@router.post(
    "/signup",
    summary="Create an account (the first account becomes the administrator)",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_login_rate_limit)],
)
async def signup(
    body: SignupRequest, response: Response, container: ContainerDep, session: SessionDep
) -> SessionOut:
    auth = AuthService(container, session)
    user = await auth.signup(body.email, body.name, body.password)
    await session.commit()
    await ProjectService(container, session).create(
        Principal(user=user),
        f"{user.name.split()[0]}'s project",
        "Your first knowledge graph. Add documents to start building it.",
    )
    _, token, claims = await auth.login(body.email, body.password)
    _set_cookie(response, container, token, claims)
    return SessionOut(user=UserOut.model_validate(user), token=token, expires_at=claims.expires_at)


@router.post("/logout", summary="Sign out", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    principal: PrincipalDep, response: Response, container: ContainerDep, session: SessionDep
) -> None:
    if principal.session is not None:
        await AuthService(container, session).logout(principal.session)
    response.delete_cookie(SESSION_COOKIE, path="/", domain=container.settings.cookie_domain)


@router.get("/me", summary="The signed-in user and their projects")
async def me(user: UserDep, container: ContainerDep, session: SessionDep) -> MeOut:
    summaries = await ProjectService(container, session).list_for(user)
    return MeOut(
        user=UserOut.model_validate(user),
        projects=[
            ProjectSummaryOut(
                id=s.project.id,
                slug=s.project.slug,
                name=s.project.name,
                role=s.role,
                document_count=s.document_count,
                entity_count=s.entity_count,
                member_count=s.member_count,
            )
            for s in summaries
        ],
    )


@router.patch("/me", summary="Update your profile")
async def update_me(
    body: ProfileUpdate, user: UserDep, container: ContainerDep, session: SessionDep
) -> UserOut:
    updated: User = await AuthService(container, session).update_profile(user, body.name)
    return UserOut.model_validate(updated)


@router.post("/password", summary="Change your password (signs out every other session)")
async def change_password(
    body: PasswordChange,
    user: UserDep,
    response: Response,
    container: ContainerDep,
    session: SessionDep,
) -> SessionOut:
    token, claims = await AuthService(container, session).change_password(
        user, body.current_password, body.new_password
    )
    _set_cookie(response, container, token, claims)
    return SessionOut(user=UserOut.model_validate(user), token=token, expires_at=claims.expires_at)
