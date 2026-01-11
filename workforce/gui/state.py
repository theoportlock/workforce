from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# Centralized GUI theme colors (cross-platform, Tk-compatible hex values)
THEME: Dict[str, Dict[str, Any]] = {
    "colors": {
        "canvas_bg": "#0D0D18",           # Darker blue-gray background for better contrast
        "text": "#FFFFFF",                # White text
        "node": {
            "running": "#0D47A1",        # Darker deep blue (better contrast)
            "ran": "#1B5E20",            # Darker forest green
            "fail": "#B71C1C",           # Darker crimson red
            "run": "#0D47A1",            # Use darker blue for 'run' readiness
            "default": "#37474F",        # Darker blue-gray for default nodes
            "selected_outline": "#FFFFFF" # White outline on selection
        },
        "edge": {
            "line": "#607D8B",           # Medium blue-gray for edges/arrows
            "drag_preview": "#607D8B",   # Temporary edge while dragging
            "select_rect": "#607D8B"     # Selection rectangle outline
        }
    }
}

@dataclass
class GUIState:
    graph: Dict[str, Any] = field(default_factory=lambda: {"nodes": [], "links": []})
    selected_nodes: List[str] = field(default_factory=list)

    scale: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    base_font_size: int = 10
    base_edge_width: int = 2

    wrapper: str = "{}"

    # interaction state
    dragging_node: Optional[str] = None
    edge_start: Optional[str] = None

    # ephemeral UI state
    _press_x: int = 0
    _press_y: int = 0
    _potential_deselect: bool = False
    _panning: bool = False
    _select_rect_active: bool = False
    _select_rect_id: Optional[int] = None
    _select_rect_start: Optional[tuple] = None
    _multi_drag_initial: Dict[str, tuple] = field(default_factory=dict)
