"""Application lifecycle loader for the configured agent graph."""

from collections.abc import Callable
from pathlib import Path

from langgraph.graph.state import CompiledStateGraph

from agent.main_agent import build_default_graph
from agent.subagents.loader import SubagentDefinition, load_subagent_definitions

GraphFactory = Callable[[tuple[SubagentDefinition, ...]], CompiledStateGraph]


class AgentLoader:
    """Loads validated subagent definitions before building the application graph."""

    def __init__(
        self,
        config_directory: Path | None = None,
        graph_factory: GraphFactory | None = None,
    ) -> None:
        self._config_directory = config_directory or (
            Path(__file__).resolve().parents[1] / "agent" / "subagents" / "configs"
        )
        self._graph_factory = graph_factory or build_default_graph
        self._definitions: tuple[SubagentDefinition, ...] | None = None

    def load_subagents(self) -> tuple[SubagentDefinition, ...]:
        """Return cached, validated declarative subagent definitions."""
        if self._definitions is None:
            self._definitions = load_subagent_definitions(self._config_directory)
        return self._definitions

    def load_agent_graph(self) -> CompiledStateGraph:
        """Load definitions before delegating graph construction."""
        return self._graph_factory(self.load_subagents())


def load_agent_graph() -> CompiledStateGraph:
    """Build the graph once application startup requires it."""
    return AgentLoader().load_agent_graph()
