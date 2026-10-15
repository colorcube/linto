"""Layout dock compatibility module.

Re-exports PaperDockWidget and TransformDockWidget.
LayoutDockWidget is maintained as an alias to TransformDockWidget.
"""

from .paper_dock import PaperDockWidget
from .transform_dock import TransformDockWidget

# Compatibility alias
LayoutDockWidget = TransformDockWidget

__all__ = ["PaperDockWidget", "TransformDockWidget", "LayoutDockWidget"]
