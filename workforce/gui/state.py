from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

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
