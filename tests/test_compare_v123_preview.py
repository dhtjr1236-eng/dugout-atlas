from types import SimpleNamespace
from ui.compare_view import CompareView

def _bundle(pitcher=False): return SimpleNamespace(profile=SimpleNamespace(is_pitcher=pitcher))

def test_hitter_compare_has_sprint_speed_as_27th_metric():
    labels=CompareView._labels_for(_bundle(),_bundle()); assert len(labels)==27; assert labels[26]=="Sprint Speed"

def test_oaa_is_integer_formatted():
    assert CompareView._format_metric("OAA",8.0)=="8"; assert CompareView._format_metric("OAA",-3.0)=="-3"

def test_sprint_speed_has_unit():
    assert CompareView._format_metric("Sprint Speed",29.36)=="29.4 ft/s"

def test_mixed_role_contract_is_unchanged():
    assert CompareView._labels_for(_bundle(False),_bundle(True))==["fWAR","bWAR","BB%","K%","xBA","xSLG","xwOBA"]
