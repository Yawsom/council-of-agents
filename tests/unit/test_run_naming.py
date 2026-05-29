from pathlib import Path

from council.artifacts.naming import build_run_dir_name, next_run_number, slugify_question


def test_slugify_question():
    assert slugify_question("Should we use Rust?") == "should-we-use-rust"
    assert slugify_question("   ") == "run"


def test_next_run_number_empty_dir(tmp_path: Path):
    assert next_run_number(tmp_path, "should-we-use-rust") == 1


def test_next_run_number_increments(tmp_path: Path):
    slug = "should-we-use-rust"
    (tmp_path / f"20250101_120000_{slug}_1").mkdir()
    (tmp_path / f"20250102_120000_{slug}_3").mkdir()
    assert next_run_number(tmp_path, slug) == 4


def test_build_run_dir_name_includes_slug_and_number(tmp_path: Path):
    question = "Should nuclear power be expanded?"
    name = build_run_dir_name(question, tmp_path)
    parts = name.split("_")
    assert parts[-1] == "1"
    assert "should-nuclear-power-be-expanded" in name
