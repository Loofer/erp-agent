"""Modal Sandbox lifecycle helpers for the agent runtime."""

import modal
from langchain_modal import ModalSandbox

MODAL_APP_NAME = "erp-agent"


def create_modal_sandbox() -> modal.Sandbox:
    """Create the application-scoped Modal Sandbox for this web worker."""
    sandbox_image = (
        modal.Image.debian_slim(python_version="3.12")
        .apt_install("git")
        .pip_install("langchain", "langgraph", "langchain-modal")
    )
    app = modal.App.lookup(
        MODAL_APP_NAME,
        environment_name="main",
        create_if_missing=True,
    )

    sandbox = modal.Sandbox.create(
        app=app,
        image=sandbox_image,
        timeout=3600,
        workdir="/root",
    )
    process = sandbox.exec("mkdir", "-p", "/sandbox")
    process.wait()
    if process.returncode != 0:
        sandbox.terminate(wait=True)
        raise RuntimeError("Unable to initialise the Modal Sandbox workspace.")
    return sandbox


def create_modal_backend(sandbox: modal.Sandbox) -> ModalSandbox:
    """Wrap a Modal Sandbox in Deep Agents' execution backend interface."""
    return ModalSandbox(sandbox=sandbox)
