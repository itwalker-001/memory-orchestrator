import json
from memory_orchestrator.ingestor import build_extraction_prompt, parse_extraction_response


def test_prompt_mentions_four_types():
    p = build_extraction_prompt(transcript_chunk="dummy", project_id="x")
    assert "user" in p and "feedback" in p and "project" in p and "reference" in p


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
