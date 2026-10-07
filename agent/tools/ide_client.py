"""HTTP calls to the IDE backend: read, validate, create, write and delete files.

Each function raises an error whose message can be shown to the user (or the
model) as is.
"""

import httpx

from agent.config import IDE_BACKEND_URL, IDE_TIMEOUT


class ReadFileError(Exception):
    """The IDE could not give us the file."""


class ValidateFileError(Exception):
    """The IDE could not validate the file."""


async def read_file(path: str) -> str:
    """Return the contents of a file in the IDE workspace.

    `path` is either a full path (`demo/app.yaml`) or just a file name, in which
    case the IDE searches the whole workspace for it. Raises ReadFileError with a
    message you can hand straight to a model.
    """
    try:
        async with httpx.AsyncClient(timeout=IDE_TIMEOUT) as client:
            response = await client.get(
                f"{IDE_BACKEND_URL}/agent/file", params={"path": path}
            )
    except httpx.HTTPError as exc:
        raise ReadFileError(
            f"cannot reach the IDE backend at {IDE_BACKEND_URL} ({exc})"
        ) from exc

    if response.status_code == 404:
        raise ReadFileError(f"{path} is not in the workspace")

    if response.status_code == 409:
        matches = ", ".join(response.json().get("matches", []))
        raise ReadFileError(
            f"several files are named {path} ({matches}) - use the full path"
        )

    if response.status_code != 200:
        raise ReadFileError(
            response.json().get("error", f"HTTP {response.status_code}")
        )

    return response.json().get("content", "")


async def validate_file(path: str) -> dict:
    """Validate a file in the IDE workspace and return the report.

    `path` is either a full path (`demo/app.yaml`) or just a file name, in which
    case the IDE searches the whole workspace for it. The report is a dict with
    `path`, `type`, `valid`, `errors` and `warnings`. Raises ValidateFileError
    with a message you can hand straight to a model.
    """
    try:
        async with httpx.AsyncClient(timeout=IDE_TIMEOUT) as client:
            response = await client.get(
                f"{IDE_BACKEND_URL}/agent/validation/file", params={"path": path}
            )
    except httpx.HTTPError as exc:
        raise ValidateFileError(
            f"cannot reach the IDE backend at {IDE_BACKEND_URL} ({exc})"
        ) from exc

    if response.status_code == 404:
        raise ValidateFileError(f"{path} is not in the workspace")

    if response.status_code == 409:
        matches = ", ".join(response.json().get("matches", []))
        raise ValidateFileError(
            f"several files are named {path} ({matches}) - use the full path"
        )

    if response.status_code != 200:
        raise ValidateFileError(
            response.json().get("error", f"HTTP {response.status_code}")
        )

    return response.json()


class WriteFileError(Exception):
    """The IDE could not write the file."""


class DeleteFileError(Exception):
    """The IDE could not delete the file."""


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    return body.get("error", f"HTTP {response.status_code}")


async def create_workspace_file(path: str, content: str) -> None:
    """Create a new file. Fails if that path already exists."""
    try:
        async with httpx.AsyncClient(timeout=IDE_TIMEOUT) as client:
            response = await client.post(
                f"{IDE_BACKEND_URL}/file/create",
                json={"path": path, "content": content},
            )
    except httpx.HTTPError as exc:
        raise WriteFileError(
            f"cannot reach the IDE backend at {IDE_BACKEND_URL} ({exc})"
        ) from exc
    if response.status_code != 200:
        raise WriteFileError(_error_message(response))


async def write_workspace_file(path: str, content: str) -> None:
    """Create or replace a file."""
    try:
        async with httpx.AsyncClient(timeout=IDE_TIMEOUT) as client:
            response = await client.post(
                f"{IDE_BACKEND_URL}/file",
                json={"path": path, "content": content},
            )
    except httpx.HTTPError as exc:
        raise WriteFileError(
            f"cannot reach the IDE backend at {IDE_BACKEND_URL} ({exc})"
        ) from exc
    if response.status_code != 200:
        raise WriteFileError(_error_message(response))


async def delete_workspace_file(path: str) -> None:
    """Delete a file or folder. The IDE panel normally does this from an action event."""
    try:
        async with httpx.AsyncClient(timeout=IDE_TIMEOUT) as client:
            response = await client.delete(
                f"{IDE_BACKEND_URL}/delete", params={"path": path}
            )
    except httpx.HTTPError as exc:
        raise DeleteFileError(
            f"cannot reach the IDE backend at {IDE_BACKEND_URL} ({exc})"
        ) from exc
    if response.status_code != 200:
        raise DeleteFileError(_error_message(response))
