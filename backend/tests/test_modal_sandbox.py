from typing import Any

from agent import sandbox as sandbox_module


class FakeImage:
    def __init__(self, calls: list[tuple[object, ...]]) -> None:
        self._calls = calls

    def apt_install(self, *packages: str) -> "FakeImage":
        self._calls.append(("apt_install", *packages))
        return self

    def pip_install(self, *packages: str) -> "FakeImage":
        self._calls.append(("pip_install", *packages))
        return self


def test_create_modal_sandbox_initializes_workspace(monkeypatch: Any) -> None:
    calls: list[tuple[object, ...]] = []
    app = object()
    image = FakeImage(calls)

    class FakeProcess:
        returncode = 0

        def wait(self) -> None:
            calls.append(("wait",))

    class FakeSandbox:
        def exec(self, *args: str) -> FakeProcess:
            calls.append(("exec", *args))
            return FakeProcess()

    sandbox = FakeSandbox()
    monkeypatch.setattr(
        sandbox_module.modal.Image,
        "debian_slim",
        lambda **kwargs: calls.append(("image", kwargs)) or image,
    )
    monkeypatch.setattr(
        sandbox_module.modal.App,
        "lookup",
        lambda name, **kwargs: calls.append(("lookup", name, kwargs)) or app,
    )
    monkeypatch.setattr(
        sandbox_module.modal.Sandbox,
        "create",
        lambda **kwargs: calls.append(("create", kwargs)) or sandbox,
    )

    assert sandbox_module.create_modal_sandbox() is sandbox
    assert calls == [
        ("image", {"python_version": "3.12"}),
        ("apt_install", "git"),
        ("pip_install", "langchain", "langgraph", "langchain-modal"),
        (
            "lookup",
            "erp-agent",
            {"environment_name": "main", "create_if_missing": True},
        ),
        (
            "create",
            {"app": app, "image": image, "timeout": 3600, "workdir": "/root"},
        ),
        ("exec", "mkdir", "-p", "/sandbox"),
        ("wait",),
    ]
