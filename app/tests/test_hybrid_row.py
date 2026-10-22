from app.storage.hybrid_row import HybridRow


def test_row_supports_numeric_and_named_access():
    row = HybridRow(["id", "company"], [7, "Example Ltd"])

    assert row[0] == 7
    assert row["company"] == "Example Ltd"
    assert dict(row) == {"id": 7, "company": "Example Ltd"}
