from graphrag.graph.names import acronym, display_name, entity_key, name_tokens


def test_keys_ignore_case_titles_possessives_and_corporate_suffixes() -> None:
    assert entity_key("Dr. Mira Okafor") == "mira okafor"
    assert entity_key("Helios Robotics Inc") == "helios robotics"
    assert entity_key("Helios Robotics's") == "helios robotics"
    assert entity_key("The Port of Rotterdam Authority") == "port of rotterdam authority"
    assert entity_key("SA\N{LATIN SMALL LETTER E WITH ACUTE}ra") == "saera"


def test_a_corporate_suffix_alone_is_kept() -> None:
    assert name_tokens("Inc") == ["inc"]


def test_display_names_drop_titles_but_keep_case() -> None:
    assert display_name("Prof. Henrik Lindgren") == "Henrik Lindgren"
    assert display_name("  Northgate   Sensors, ") == "Northgate Sensors"


def test_acronyms_are_the_initials_of_multiword_names() -> None:
    assert acronym("Helios Robotics Institute") == "hri"
    assert acronym("Port of Rotterdam Authority") == "pra"
    assert acronym("Helios") == ""
