from services.compare_league_context import percentile

def test_percentile_uses_population_distribution():
    assert percentile(.275,[.200,.225,.250,.275]) == 100.0
    assert percentile(.250,[.200,.225,.250,.275]) == 75.0

def test_percentile_handles_missing_inputs():
    assert percentile(None,[1,2]) is None
    assert percentile(1,[]) is None
