"""
Grid Level Calculator

Computes entry and target prices for each grid level on both
buy and sell sides, incorporating the geometric doubling of
spacing and target per subset.

Key property: all buy targets converge to anchor + base_space,
all sell targets converge to anchor - base_space.
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
    grid_space: float   # spacing for this subset
    target_offset: float  # target distance from entry


class GridCalculator:
    """
    Computes grid levels for buy and sell sides.

    Buy levels are placed below anchor, sell levels above.
    Spacing and target double with each successive subset.
    """

    def __init__(self, config: GridConfig):
        self.config = config
        self.subsets = config.compute_subsets()

    def compute_buy_levels(self) -> List[GridLevel]:
        """
        Compute buy entry levels below anchor price.

        Level i entry = anchor - cumulative_distance[i]
        Level i target = entry + target_offset[i]

        All targets converge to anchor + base_grid_space.
        """
        levels = []
        for s in self.subsets:
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

    def compute_sell_levels(self) -> List[GridLevel]:
        """
        Compute sell entry levels above anchor price.

        Level i entry = anchor + cumulative_distance[i]
        Level i target = entry - target_offset[i]

        All targets converge to anchor - base_grid_space.
        """
        levels = []
        for s in self.subsets:
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
