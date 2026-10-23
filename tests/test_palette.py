"""The Weather Impact 2.0 palette rules and how older project colors snap to it."""
import pytest

from palette import GRID_PALETTE, PALETTE, TEXT_COLORS, nearest_color, snap_settings

SETS = {'last_c1': PALETTE, 'grid_color': GRID_PALETTE}


@pytest.mark.parametrize("old, name", [
    ("#045EA8", "Blue"), ("#FFD700", "Yellow"), ("#E63946", "Breaking Red"), ("#000000", "WI Navy"),
    ("#FFFFFF", "White"), ("#9A9A9A", "Gray"), ("#2CA02C", "Green"), ("#59c8ff", "Highlight Blue"),
])
def test_nearest_color(old, name):
    assert nearest_color(old.upper(), PALETTE)[0] == name


def test_restricted_sets():
    assert list(TEXT_COLORS) == ["White", "WI Navy"]
    assert list(GRID_PALETTE) == ["White", "WI Navy", "Gray"]
    assert len(PALETTE) == 9


def test_snap_settings_changes_only_off_palette_restricted_colors():
    settings = {'last_c1': "#045EA8", 'grid_color': "#FF6B6B", 'rb_normal_color': "#E0C084",
                'text_choice': "Black"}
    notes = snap_settings(settings, SETS)
    assert settings == {'last_c1': "#285DA3", 'grid_color': "#A3BCC6", 'rb_normal_color': "#E0C084",
                        'text_choice': "WI Navy"}
    assert notes == ["#045EA8 → Blue", "#FF6B6B → Gray"]


def test_snap_settings_leaves_palette_colors_alone():
    settings = {'last_c1': "#d71b32", 'grid_color': "#022E67", 'text_choice': "White"}
    assert snap_settings(settings, SETS) == [] and settings['last_c1'] == "#d71b32"


def test_gradients():
    from palette import GRADIENTS, contrast_text, gradient_stops, solid
    assert gradient_stops(GRADIENTS["Navy Gradient"]) == ("#045EA8", "#022E67")
    assert gradient_stops("#285DA3") is None
    assert solid(GRADIENTS["Highlight Blue Gradient"]) == "#59C8FF" and solid("#285DA3") == "#285DA3"
    # The style sheet's "proper contrast": White on navy and red, WI Navy on Highlight Blue
    assert [contrast_text(g) for g in GRADIENTS.values()] == ["#FFFFFF", "#022E67", "#FFFFFF"]
    assert contrast_text("#FFD633") == "#022E67" and contrast_text("#285DA3") == "#FFFFFF"


def test_gradients_never_snap_targets():
    from palette import BAR_PALETTE
    assert nearest_color("#045EA8", BAR_PALETTE)[0] == "Blue"
