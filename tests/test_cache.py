from app.providers.cache import DiskCache


def test_disk_cache_roundtrip(tmp_path):
    c = DiskCache(tmp_path)
    assert c.get("/fixtures", {"date": "2026-05-01"}) is None
    c.set("/fixtures", {"date": "2026-05-01"}, {"response": [1, 2, 3]})
    assert c.get("/fixtures", {"date": "2026-05-01"}) == {"response": [1, 2, 3]}


def test_disk_cache_key_isolation(tmp_path):
    c = DiskCache(tmp_path)
    c.set("/odds", {"fixture": 1}, {"a": 1})
    c.set("/odds", {"fixture": 2}, {"a": 2})
    assert c.get("/odds", {"fixture": 1}) == {"a": 1}
    assert c.get("/odds", {"fixture": 2}) == {"a": 2}
