from memory_orchestrator_server.ingestor import read_transcript_incremental


def test_reads_from_offset(tmp_path):
    f = tmp_path / "t.jsonl"
    f.write_text('{"role":"user","content":"a"}\n{"role":"assistant","content":"b"}\n')
    lines, new_offset = read_transcript_incremental(str(f), offset=0)
    assert len(lines) == 2
    assert new_offset == 2
    lines2, offset2 = read_transcript_incremental(str(f), offset=new_offset)
    assert lines2 == []
    assert offset2 == 2


def test_resumes_after_append(tmp_path):
    f = tmp_path / "t.jsonl"
    f.write_text('{"role":"user","content":"a"}\n')
    _, offset = read_transcript_incremental(str(f), offset=0)
    with f.open("a") as h:
        h.write('{"role":"user","content":"b"}\n')
    lines, new_offset = read_transcript_incremental(str(f), offset=offset)
    assert len(lines) == 1
    assert new_offset == 2


def test_missing_file_returns_empty(tmp_path):
    lines, offset = read_transcript_incremental(str(tmp_path / "nope.jsonl"), offset=5)
    assert lines == []
    assert offset == 5
