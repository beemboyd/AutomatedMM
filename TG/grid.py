"""
Grid Level Calculator

Computes entry and target prices for each grid level on both
buy and sell sides with uniform spacing.

Supports dynamic spacing via grid_space parameter for
epoch-based reanchor (spacing increases every N reanchors).
"""

from dataclasses import dataclass
from typing import List

from .config import GridConfig


@dataclass
class GridLevel:
    """A single grid level with entry and target prices."""
    subset_index: int
    side: str           # "BUY" or "SELL"
    entry_price: float
    target_price: float
    qty: int
    grid_space: float   # spacing for this level
    target_offset: float  # target distance from entry


class GridCalculator:
    """
    Computes grid levels for buy and sell sides.

    Buy levels are placed below anchor, sell levels above.
    Uniform spacing within each computation; spacing can vary
    between buy and sell sides via the grid_space parameter.
    """

    def __init__(self, config: GridConfig):
        self.config = config

    def compute_buy_levels(self, grid_space: float = None) -> List[GridLevel]:
        """
        Compute buy entry levels below anchor price.

        Level i entry = anchor - grid_space * (i + 1)
        Level i target = entry + base_target

        Args:
            grid_space: Override spacing for buy side. Defaults to base_grid_space.
        """
        subsets = self.config.compute_subsets(grid_space=grid_space)
        levels = []
        for s in subsets:
            entry = round(self.config.anchor_price - s.distance_from_anchor, 2)
            target = round(entry + s.target, 2)
            levels.append(GridLevel(
                subset_index=s.index,
                side="BUY",
                entry_price=entry,
                target_price=target,
                qty=s.qty,
                grid_space=s.grid_space,
                target_offset=s.target,
            ))
        return levels

    def compute_sell_levels(self, grid_space: float = None) -> List[GridLevel]:
        """
        Compute sell entry levels above anchor price.

        Level i entry = anchor + grid_space * (i + 1)
        Level i target = entry - base_target

        Args:
            grid_space: Override spacing for sell side. Defaults to base_grid_space.
        """
        subsets = self.config.compute_subsets(grid_space=grid_space)
        levels = []
        for s in subsets:
            entry = round(self.config.anchor_price + s.distance_from_anchor, 2)
            target = round(entry - s.target, 2)
            levels.append(GridLevel(
                subset_index=s.index,
                side="SELL",
                entry_price=entry,
                target_price=target,
                qty=s.qty,
                grid_space=s.grid_space,
                target_offset=s.target,
            ))
        return levels
