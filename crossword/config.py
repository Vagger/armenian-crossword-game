"""Load and validate puzzle rules without coupling them to a solver."""

from dataclasses import dataclass, field
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class GridConfig:
    rows: int = 20
    columns: int = 20

    def __post_init__(self) -> None:
        for name in ("rows", "columns"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"grid.{name} must be a positive integer")


@dataclass(frozen=True)
class CrosswordConfig:
    language: str = "en"
    grid: GridConfig = field(default_factory=GridConfig)
    directions: tuple[str, ...] = ("across", "down")
    require_all_words: bool = True
    require_connected: bool = True
    allow_side_touching: bool = False
    allow_diagonal_touching: bool = True
    allow_duplicate_words: bool = False

    def __post_init__(self) -> None:
        if self.language != "en":
            raise ValueError("Only language 'en' is supported currently; Armenian is planned")
        if not isinstance(self.grid, GridConfig):
            raise ValueError("grid must be a GridConfig")
        if (
            not isinstance(self.directions, tuple)
            or not self.directions
            or any(d not in ("across", "down") for d in self.directions)
            or len(set(self.directions)) != len(self.directions)
        ):
            raise ValueError("directions must be a nonempty tuple of unique across/down values")
        for name in (
            "require_all_words", "require_connected", "allow_side_touching",
            "allow_diagonal_touching", "allow_duplicate_words",
        ):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a boolean")


def load_config(path: str | Path = "config.toml") -> CrosswordConfig:
    """Read TOML rules; omitted fields use defaults and unknown fields fail."""
    with Path(path).open("rb") as source:
        data = tomllib.load(source)

    unknown = data.keys() - CrosswordConfig.__dataclass_fields__.keys()
    if unknown:
        raise ValueError(f"Unknown configuration fields: {', '.join(sorted(unknown))}")

    grid = data.pop("grid", {})
    if not isinstance(grid, dict):
        raise ValueError("grid must be a table with rows and columns")
    unknown_grid = grid.keys() - GridConfig.__dataclass_fields__.keys()
    if unknown_grid:
        raise ValueError(f"Unknown grid fields: {', '.join(sorted(unknown_grid))}")
    if "directions" in data:
        if not isinstance(data["directions"], list):
            raise ValueError("directions must be an array")
        data["directions"] = tuple(data["directions"])
    return CrosswordConfig(grid=GridConfig(**grid), **data)
