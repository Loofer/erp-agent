"""Application lifecycle loader for the configured agent graph."""

from collections.abc import Callable
from pathlib import Path

from langgraph.graph.state import CompiledStateGraph

from agent.config import load_settings
from agent.main_agent import create_main_agent
from agent.subagents.loader import SubagentDefinition, load_subagent_definitions

AgentFactory = Callable[..., CompiledStateGraph]


class AgentLoader:
    """Loads validated subagent definitions before building the application graph."""

    def __init__(
        self,
        config_directory: Path | None = None,
        agent_factory: AgentFactory | None = None,
        model: str | None = None,
    ) -> None:
        self._config_directory = config_directory or (
            Path(__file__).resolve().parents[1] / "agent" / "subagents" / "configs"
        )
        self._agent_factory = agent_factory or create_main_agent
        self._model = model or load_settings().model
        self._definitions: tuple[SubagentDefinition, ...] | None = None

    def load_subagents(self) -> tuple[SubagentDefinition, ...]:
        """Return cached, validated declarative subagent definitions."""
        if self._definitions is None:
            self._definitions = load_subagent_definitions(self._config_directory)
        return self._definitions

    def load_agent_graph(self) -> CompiledStateGraph:
        """Load definitions before delegating graph construction."""
        return self._agent_factory(self._model, subagents=self.load_subagents())


def load_agent_graph() -> CompiledStateGraph:
    """Build the graph once application startup requires it."""
    return AgentLoader().load_agent_graph()
