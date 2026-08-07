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
    assert "supplier_manager" in memory_guide.read_text(encoding="utf-8")
    assert "supplier_query" in analysis_guide.read_text(encoding="utf-8")
    assert "create_supplier" in supplier_guide.read_text(encoding="utf-8")
    assert "request_supplier_info" in supplier_guide.read_text(encoding="utf-8")
