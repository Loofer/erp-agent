import pytest

from visualization.schema import ChartDocumentError, parse_chart_documents


def test_parse_chart_documents_ignores_ordinary_stdout() -> None:
    assert parse_chart_documents("count=3\nfinished") == []


def test_parse_chart_documents_extracts_chart_ndjson() -> None:
    stdout = (
        "finished\n"
        '{"type":"chart","version":"1.0","charts":[{'
        '"id":"trend","chart_type":"line","title":"Price trend",'
        '"x":"month","y":"price","data":[{"month":"2026-01","price":10}]}]}'
    )

    charts = parse_chart_documents(stdout)

    assert len(charts) == 1
    assert charts[0].id == "trend"


def test_parse_chart_documents_rejects_missing_row_axis_fields() -> None:
    stdout = (
        '{"type":"chart","version":"1.0","charts":[{'
        '"id":"trend","chart_type":"line","title":"Price trend",'
        '"x":"month","y":"price","data":[{"month":"2026-01"}]}]}'
    )

    with pytest.raises(ChartDocumentError):
        parse_chart_documents(stdout)
