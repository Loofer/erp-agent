from pathlib import Path


def test_skill_documents_describe_current_tools_and_native_approval() -> None:
    root = Path(__file__).resolve().parents[1] / "skills"
    memory_guide = Path(__file__).resolve().parents[1] / "src" / "agent" / "memory" / "AGENTS.md"
    management_guide = root / "main" / "skill-management" / "SKILL.md"
    analysis_guide = root / "procurement" / "procurement-analysis" / "SKILL.md"
    supplier_guide = root / "supplier" / "supplier-management" / "SKILL.md"

    assert memory_guide.is_file()
    assert management_guide.is_file()
    assert analysis_guide.is_file()
    assert supplier_guide.is_file()
    memory_content = memory_guide.read_text(encoding="utf-8")
    assert "supplier_manager" in memory_content
    assert "/memory/AGENTS.md" in memory_content
    assert "/memories/preferences.md" in memory_content
    assert "config.configurable.user_id" in memory_content
    assert "持久化到 `/per`" not in memory_content
    assert "assign_skill" not in memory_content
    assert "supplier_query" in analysis_guide.read_text(encoding="utf-8")
    assert "chart_params.md" in analysis_guide.read_text(encoding="utf-8")
    assert "不得为图表安装或使用 `matplotlib`" in analysis_guide.read_text(encoding="utf-8")
    assert "引号不得添加多余反斜杠" in analysis_guide.read_text(encoding="utf-8")
    assert "create_supplier" in supplier_guide.read_text(encoding="utf-8")
    assert "request_supplier_info" in supplier_guide.read_text(encoding="utf-8")
