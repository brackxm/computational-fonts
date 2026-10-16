"""Project paths shared by the builder, runner, and regression tests."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FONT = ROOT / 'ski.ttf'
DISPLAY_FONT = ROOT / 'ski-font.ttf'
