import uuid

from loan_engine import batches


def test_recent_lists_newest_first_with_uploader(conn):
    older, newer = str(uuid.uuid4()), str(uuid.uuid4())
    batches.create(conn, older, "uploads/a.csv", "a.csv", "asha@example.com")
    conn.run("update upload_batches set created_at = now() - interval '1 hour'")
    batches.create(conn, newer, "uploads/b.csv", "b.csv", "ravi@example.com")

    listed = batches.recent(conn)

    assert [str(row["batch_id"]) for row in listed] == [newer, older]
    assert (listed[0]["file_name"], listed[0]["uploaded_by"]) == ("b.csv", "ravi@example.com")
