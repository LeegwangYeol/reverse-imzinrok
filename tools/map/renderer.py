"""Imjinrok 2+ Dawn 2D Minimap Preview Renderer.

Generates high-quality 2D minimap PNG previews from .map binary data using Pillow.
Visualizes:
- Theme-aware ground, cliff, and water palettes
- Subtle elevation shading
- Resource nodes (tree, bamboo, potato, rice, neutral landmarks)
- Pre-placed buildings with player owner coloring
- High-visibility player starting position emblems with player colors and outlines
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

from tools.map.parser import (
    MAX_MAP_DIMENSION,
    MapData,
    PlayerStart,
    parse_map,
)

# Standard Player Colors (Match Imjinrok 2+ Minimap UI)
PLAYER_COLORS: List[Tuple[int, int, int]] = [
    (0, 110, 255),  # Player 0: Royal Blue
    (255, 35, 35),  # Player 1: Crimson Red
    (255, 230, 20),  # Player 2: Bright Yellow
    (20, 215, 35),  # Player 3: Emerald Green
    (195, 45, 255),  # Player 4: Purple / Violet
    (255, 135, 10),  # Player 5: Tangerine Orange
    (15, 225, 255),  # Player 6: Sky Cyan
    (255, 105, 185),  # Player 7: Hot Pink
]

NEUTRAL_COLOR = (210, 210, 210)

# Theme Palette Definitions
THEME_PALETTES: Dict[int, Dict[str, Tuple[int, int, int]]] = {
    0: {  # Normal (Temperate plain)
        "water": (45, 95, 165),
        "water_deep": (35, 75, 135),
        "ground": (145, 130, 95),
        "cliff": (110, 95, 75),
    },
    1: {  # Snow (Snowfield / Ice)
        "water": (65, 120, 180),
        "water_deep": (50, 95, 150),
        "ground": (225, 235, 245),
        "cliff": (145, 155, 170),
    },
    2: {  # Brown (Wasteland / Clay)
        "water": (45, 85, 145),
        "water_deep": (35, 65, 115),
        "ground": (175, 135, 90),
        "cliff": (115, 85, 55),
    },
    3: {  # Green (Grassland / Dense Jungle)
        "water": (40, 95, 155),
        "water_deep": (30, 75, 125),
        "ground": (110, 150, 75),
        "cliff": (80, 105, 60),
    },
    4: {  # Dark (Rocky Night Battlefield)
        "water": (35, 65, 115),
        "water_deep": (25, 50, 90),
        "ground": (95, 90, 100),
        "cliff": (65, 60, 70),
    },
    5: {  # Volcano (Volcano Rock / Ash)
        "water": (45, 55, 85),
        "water_deep": (30, 40, 65),
        "ground": (115, 95, 90),
        "cliff": (70, 55, 50),
    },
    6: {  # Bright (Desert / Sand / Beach)
        "water": (50, 125, 195),
        "water_deep": (35, 100, 160),
        "ground": (210, 185, 130),
        "cliff": (160, 130, 85),
    },
}

# Resource Colors
RESOURCE_COLORS: Dict[int, Tuple[int, int, int]] = {
    1: (220, 160, 35),  # Potato: Amber Gold
    2: (45, 165, 45),  # Bamboo: Bright Bamboo Green
    3: (25, 105, 30),  # Tree / Forest: Deep Forest Green
    100: (235, 210, 45),  # Rice: Golden Grain
}


def _clamp_color(r: int, g: int, b: int) -> Tuple[int, int, int]:
    return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def render_minimap_image(
    map_data: Union[MapData, str, Path],
    width: int = 400,
    height: int = 400,
    show_players: bool = True,
    show_resources: bool = True,
    show_buildings: bool = True,
) -> Image.Image:
    """Renders a 2D minimap image and returns the PIL Image object.

    Args:
        map_data: MapData object or path to .map file.
        width: Output image width in pixels (default 400).
        height: Output image height in pixels (default 400).
        show_players: Whether to render player starting location markers.
        show_resources: Whether to render resource deposits.
        show_buildings: Whether to render pre-placed buildings.

    Returns:
        PIL.Image.Image in RGB mode.
    """
    if not isinstance(map_data, MapData):
        map_data = parse_map(map_data)

    map_w, map_h = map_data.width, map_data.height
    theme_palette = THEME_PALETTES.get(map_data.theme_id, THEME_PALETTES[0])

    # 1. Render base grid at native 1:1 map resolution
    base_img = Image.new("RGB", (map_w, map_h))
    pixels = base_img.load()

    for y in range(map_h):
        for x in range(map_w):
            t_type = map_data.get_terrain_type(x, y)
            t_walk = map_data.get_walkability(x, y)
            elev = map_data.get_elevation(x, y)
            depth = map_data.get_water_depth(x, y)

            if t_type == 1:
                # Water
                if depth > 4:
                    col = theme_palette["water_deep"]
                else:
                    col = theme_palette["water"]
            else:
                # Ground
                if t_walk != 0:
                    col = theme_palette["cliff"]
                else:
                    col = theme_palette["ground"]

                # Subtle elevation lighting (+4 per level)
                if elev > 0:
                    delta = elev * 4
                    col = _clamp_color(col[0] + delta, col[1] + delta, col[2] + delta)

            # 2. Overlay resources
            if show_resources:
                res = map_data.get_resource(x, y)
                if res is not None:
                    if res.type_id in RESOURCE_COLORS:
                        col = RESOURCE_COLORS[res.type_id]
                    else:
                        col = (165, 145, 185)  # Neutral landmarks/objects

            # 3. Overlay pre-placed buildings
            if show_buildings:
                bldg = map_data.get_building(x, y)
                if bldg is not None:
                    if bldg.owner_id < len(PLAYER_COLORS):
                        col = PLAYER_COLORS[bldg.owner_id]
                    else:
                        col = NEUTRAL_COLOR

            pixels[x, y] = col

    # 4. Scale up cleanly to target dimensions using Nearest Neighbor
    # to preserve RTS minimap tile sharpness
    out_img = base_img.resize((width, height), Image.NEAREST)
    draw = ImageDraw.Draw(out_img)

    # 5. Overlay high-visibility player start markers
    if show_players:
        scale_x = width / map_w
        scale_y = height / map_h
        marker_radius = max(4, int(min(scale_x, scale_y) * 2.5))

        for start in map_data.get_active_player_starts():
            cx = int((start.x + 0.5) * scale_x)
            cy = int((start.y + 0.5) * scale_y)
            p_color = PLAYER_COLORS[start.player_id % len(PLAYER_COLORS)]

            # Outer black shadow / border
            draw.ellipse(
                [
                    (cx - marker_radius - 2, cy - marker_radius - 2),
                    (cx + marker_radius + 2, cy + marker_radius + 2),
                ],
                fill=(10, 10, 10),
            )

            # White outline
            draw.ellipse(
                [
                    (cx - marker_radius - 1, cy - marker_radius - 1),
                    (cx + marker_radius + 1, cy + marker_radius + 1),
                ],
                fill=(255, 255, 255),
            )

            # Inner player color
            draw.ellipse(
                [(cx - marker_radius, cy - marker_radius), (cx + marker_radius, cy + marker_radius)],
                fill=p_color,
            )

            # Center white dot
            inner_dot = max(1, marker_radius // 3)
            draw.ellipse(
                [(cx - inner_dot, cy - inner_dot), (cx + inner_dot, cy + inner_dot)],
                fill=(255, 255, 255),
            )

    return out_img


def render_minimap(
    map_data: Union[MapData, str, Path],
    output_png_path: Optional[Union[str, Path]] = None,
    width: int = 400,
    height: int = 400,
    show_players: bool = True,
    show_resources: bool = True,
    show_buildings: bool = True,
) -> bool:
    """Renders a minimap preview and saves it to output_png_path.

    Matches interface contract:
    render_minimap(map_data, output_png_path, width=400, height=400) -> bool

    Args:
        map_data: MapData object or path to .map file.
        output_png_path: Target PNG file path.
        width: Width in pixels (default 400).
        height: Height in pixels (default 400).
        show_players: Whether to render player starting location markers.
        show_resources: Whether to render resource deposits.
        show_buildings: Whether to render pre-placed buildings.

    Returns:
        True on success.
    """
    img = render_minimap_image(
        map_data=map_data,
        width=width,
        height=height,
        show_players=show_players,
        show_resources=show_resources,
        show_buildings=show_buildings,
    )

    if output_png_path is not None:
        out_path = Path(output_png_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, format="PNG")

    return True
