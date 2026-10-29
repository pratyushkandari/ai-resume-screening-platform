"""Start-up schema preparation for databases created by earlier versions."""

from sqlalchemy import create_engine, inspect, text

from app.schema import add_missing_columns


def test_add_missing_columns_upgrades_an_old_resumes_table(tmp_path):
    old = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with old.begin() as conn:
        conn.execute(text("CREATE TABLE resumes (resume_id INTEGER PRIMARY KEY, filename TEXT)"))
        conn.execute(text("INSERT INTO resumes (resume_id, filename) VALUES (1, 'cv.txt')"))
    add_missing_columns(old)
    add_missing_columns(old)  # running again is a no-op
    assert "semantic_score" in {column["name"] for column in inspect(old).get_columns("resumes")}
    with old.connect() as conn:
        assert conn.execute(text("SELECT semantic_score FROM resumes")).scalar() is None
    old.dispose()
