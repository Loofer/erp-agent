from pathlib import Path


def test_skill_documents_describe_current_tools_and_native_approval() -> None:
    root = Path(__file__).resolve().parents[1] / "skills"
    main_guide = root / "main" / "AGENTS.md"
    management_guide = root / "main" / "skill-management" / "SKILL.md"
    analysis_guide = root / "procurement" / "procurement-analysis" / "SKILL.md"

    assert main_guide.is_file()
    assert management_guide.is_file()
    assert analysis_guide.is_file()
    assert "create_supplier" in main_guide.read_text(encoding="utf-8")
    assert "human approval" in main_guide.read_text(encoding="utf-8")
    assert "get_dashboard" in analysis_guide.read_text(encoding="utf-8")
