import pytest

from app.theme import PALETTES


def _luminance(color):
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
              for value in channels]
    return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


@pytest.mark.parametrize('mode', ['light', 'dark'])
def test_normal_text_and_interactive_labels_meet_aa_contrast(mode):
    colors = PALETTES[mode]
    for foreground, background in [
        ('ink', 'paper'), ('body', 'paper'), ('muted', 'paper'), ('subtle', 'paper'),
        ('ink', 'surface'), ('muted', 'surface'), ('link', 'paper'),
        ('active-ink', 'active'), ('on-primary', 'primary'),
        ('positive', 'positive-bg'), ('card-muted', 'card'),
        ('ink', 'panel'), ('body', 'panel'), ('muted', 'panel'),
    ]:
        darker, lighter = sorted((_luminance(colors[foreground]), _luminance(colors[background])))
        ratio = (lighter + 0.05) / (darker + 0.05)
        assert ratio >= 4.5, f'{mode}: {foreground} on {background} has contrast {ratio:.2f}'


@pytest.mark.parametrize('mode', ['light', 'dark'])
def test_chart_marks_have_accessible_contrast_on_raised_panels(mode):
    colors = PALETTES[mode]
    for tone in ('blue', 'purple', 'teal', 'amber', 'clay', 'slate'):
        darker, lighter = sorted((_luminance(colors['tone-' + tone]), _luminance(colors['panel'])))
        assert (lighter + .05) / (darker + .05) >= 3, f'{mode}: {tone} mark contrast'
