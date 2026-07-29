# Backend Architecture

`main.py` and `bootstrap.py` expose the ASGI application. `src/api_view` owns
HTTP composition and routers. `src/agent` owns graph orchestration, direct API
tools, approval middleware, and explicit workflows. The tool boundary is
in-process Python; state-changing requests are staged and approved before the
client can send the representative supplier-create request.

`skills`, `test`, `configs`, `data`, `logs`, and `scripts` are intentionally
reserved extension directories.
