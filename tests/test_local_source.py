def test_local_source_loads_every_page_with_titles(source):
    docs = source.load_all()
    titles = {d.metadata["title"] for d in docs}
    assert "Atlas AMR Overview" in titles and "Safety System" in titles
    assert all(d.metadata["source"] == "local" for d in docs)
    assert all("#chunk" in d.doc_id for d in docs)


def test_obsolete_page_is_skipped(source):
    assert source.load_one("obsolete-legacy-dock.md") == []
    assert all(d.metadata["title"] != "Obsolete Legacy Dock Procedure" for d in source.load_all())


def test_load_one_matches_subset_of_load_all(source):
    one = source.load_one("safety.md")
    everything = source.load_all()
    assert {d.doc_id for d in one} <= {d.doc_id for d in everything}
