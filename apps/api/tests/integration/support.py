"""HTTP helpers shared by the integration tests."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from graphrag.demo.corpus import NOTES
from graphrag.integrations.queue import InlineQueue

PASSWORD = "Integration-pass-2026"


@dataclass(frozen=True)
class Account:
    email: str
    user_id: str
    token: str
    project: str  # slug of the first project created at sign-up

    @property
    def headers(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.token}"}


def bearer(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


async def signup(client: httpx.AsyncClient, name: str = "Test Person") -> Account:
    email = f"{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post(
        "/api/v1/auth/signup", json={"email": email, "name": name, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    token = response.json()["token"]
    # Bearer tokens only: a cookie left in the shared client would authenticate later calls.
    client.cookies.clear()
    me = (await client.get("/api/v1/auth/me", headers=bearer(token))).json()
    return Account(email, me["user"]["id"], token, me["projects"][0]["slug"])


async def settle(client: httpx.AsyncClient) -> None:
    """Wait for every job, including jobs enqueued by jobs, to finish."""
    queue = client.container.queue  # type: ignore[attr-defined]
    assert isinstance(queue, InlineQueue)
    await queue.drain()


async def add_member(
    client: httpx.AsyncClient, owner: Account, project: str, member: Account, role: str
) -> None:
    response = await client.post(
        f"/api/v1/projects/{project}/members",
        json={"email": member.email, "role": role},
        headers=owner.headers,
    )
    assert response.status_code == 201, response.text


async def import_texts(
    client: httpx.AsyncClient, account: Account, project: str, items: list[dict[str, Any]]
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/projects/{project}/documents/import",
        json={"items": items},
        headers=account.headers,
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def import_notes(client: httpx.AsyncClient, account: Account, project: str) -> dict[str, Any]:
    return await import_texts(
        client,
        account,
        project,
        [
            {
                "type": "text",
                "title": note.title,
                "text": note.body,
                "format": "markdown",
                "external_id": note.slug,
            }
            for note in NOTES
        ],
    )


async def get_json(client: httpx.AsyncClient, account: Account, path: str, **params: Any) -> Any:
    response = await client.get(path, params=params or None, headers=account.headers)
    assert response.status_code == 200, f"{path}: {response.status_code} {response.text}"
    return response.json()
