import json
from memory_orchestrator.ingestor import build_extraction_prompt, parse_extraction_response


def test_prompt_mentions_four_types():
    from memory_orchestrator.ingestor import EXTRACTION_SYSTEM_PROMPT
    assert "user" in EXTRACTION_SYSTEM_PROMPT
    assert "feedback" in EXTRACTION_SYSTEM_PROMPT
    assert "project" in EXTRACTION_SYSTEM_PROMPT
    assert "reference" in EXTRACTION_SYSTEM_PROMPT


def test_parse_valid_json_array():
    raw = json.dumps([
        {
            "type": "feedback", "name": "no-mocks",
            "description": "use real DB", "content": "longer text",
            "why": "past incident", "how_to_apply": "all integration tests",
            "importance": 5,
        }
    ])
    items = parse_extraction_response(raw)
    assert len(items) == 1
    assert items[0]["type"] == "feedback"


def test_parse_strips_markdown_fence():
    raw = "```json\n[]\n```"
    assert parse_extraction_response(raw) == []


def test_parse_drops_invalid_types():
    raw = json.dumps([{"type": "bogus", "name": "x", "description": "x", "content": "x"}])
    assert parse_extraction_response(raw) == []


def test_parse_drops_missing_required_for_feedback():
    raw = json.dumps([
        {"type": "feedback", "name": "x", "description": "x", "content": "x"}
    ])
    assert parse_extraction_response(raw) == []
