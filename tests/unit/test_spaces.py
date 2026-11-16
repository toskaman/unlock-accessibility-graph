"""Lift-description parsing on real strings observed in the SNCF NeTEx file."""
from unlock.ingest import spaces


def roles(desc, codes):
    t = spaces.derive("s", set(codes), [("L", "L", desc)])
    return sorted((f.space_id.split(":", 1)[1], f.derivation) for f in t.serves), t


def test_two_sided_voie_and_connector():
    r, t = roles("Voie 1 / souterrain", {"1", "2"})
    assert r == [("quay:1", "VOIE_TOKEN"), ("space:souterrain", "NAMED_SPACE")]
    assert t.spaces["s:space:souterrain"].role == "CONNECTOR"


def test_island_platform_serves_both_tracks():
    r, _ = roles("Voies C et D / passerelle", {"c", "d", "e"})
    assert ("quay:c", "VOIE_TOKEN") in r and ("quay:d", "VOIE_TOKEN") in r


def test_bis_maps_to_b_suffix():
    r, _ = roles("Voies 2 et 2bis / passerelle", {"2", "2b"})
    assert ("quay:2b", "VOIE_TOKEN") in r


def test_range_of_tracks():
    r, _ = roles("Hall 3 niveau 3 voies 25 à 28 / hall", {"25", "26", "27", "28"})
    assert {x for x, _ in r if x.startswith("quay")} == {"quay:25", "quay:26", "quay:27", "quay:28"}


def test_exit_and_mojibake():
    r, t = roles("Dalle routià¨re / passerelle", {"1"})
    assert t.spaces["s:space:dalle-routiere"].role == "EXIT"


def test_single_sided_gets_unconnected_placeholder():
    r, t = roles("Quai 2 direction Province", {"1", "2"})
    assert ("quay:2", "QUAI_NUMBER") in r
    assert any(d == "UNSPECIFIED_END" for _, d in r)


def test_unknown_track_is_not_invented():
    r, t = roles("Voie Z / souterrain", {"1", "2"})
    assert not any(x.startswith("quay") for x, _ in r)
    assert ("L", "z") in t.unmatched_tokens


def test_word_is_not_a_track_code():
    r, _ = roles("Voies transmanche / hall", {"tr", "1"})
    assert not any(x == "quay:tr" for x, _ in r)


def test_platform_text_without_match_is_not_exit():
    _, t = roles("Quai A sortie rue du Bac", {"1", "2"})
    assert t.spaces["s:space:quai-a-sortie-rue-du-bac"].role == "UNRESOLVED_PLATFORM"
