"""Provider-side Blender L2 infographic handlers.

All native backends are narrow, bounded functions. The bridge adds op_id receipts
and injects allow_roots from workstation policy. Never accepts an arbitrary bpy
method, node type, or externally supplied allow_roots.
"""

from __future__ import annotations

from .infographic_geometry import create_particle_preset
from .infographic_geometry_grid import create_animated_particle_grid
from .infographic_grease import create_grease_strokes
from .infographic_grease_tween import create_filled_grease_tween
from .infographic_shaped_plane import create_shaped_text_plane
from .infographic_svg import import_svg_curves
from .infographic_unicode import create_unicode_text


class InfographicTools:
    def import_svg_curves(
        self,
        filepath,
        prefix,
        target_width=None,
        location=None,
        _allow_roots=None,
    ):
        return import_svg_curves(
            filepath,
            prefix=prefix,
            target_width=target_width,
            location=location,
            allow_roots=_allow_roots or [],
        )

    def create_grease_strokes(
        self,
        name,
        strokes,
        color="#5CEBFF",
        radius=0.045,
        start_frame=1,
        end_frame=None,
        steps=1,
    ):
        return create_grease_strokes(
            name,
            strokes=strokes,
            color=color,
            radius=radius,
            start_frame=start_frame,
            end_frame=end_frame,
            steps=steps,
        )

    def create_filled_grease_tween(
        self,
        name,
        start_strokes,
        end_strokes,
        start_frame=1,
        end_frame=45,
        steps=12,
        fill_color="#42BDFB",
        outline_color="#A0EEFF",
        radius=0.03,
        easing="SMOOTHSTEP",
    ):
        return create_filled_grease_tween(
            name,
            start_strokes=start_strokes,
            end_strokes=end_strokes,
            start_frame=start_frame,
            end_frame=end_frame,
            steps=steps,
            fill_color=fill_color,
            outline_color=outline_color,
            radius=radius,
            easing=easing,
        )

    def create_particle_preset(
        self,
        name,
        mode="LINE",
        count=25,
        radius=0.04,
        color="#53E9FF",
        start=(-2, 0, 0),
        end=(2, 0, 0),
        ring_radius=1.0,
        frame_start=1,
        frame_end=60,
    ):
        return create_particle_preset(
            name,
            mode=mode,
            count=count,
            radius=radius,
            color=color,
            start=start,
            end=end,
            ring_radius=ring_radius,
            frame_start=frame_start,
            frame_end=frame_end,
        )

    def create_animated_particle_grid(
        self,
        name,
        rows=8,
        columns=14,
        spacing=0.25,
        amplitude=0.22,
        particle_radius=0.035,
        color="#77E5FF",
        start_frame=1,
        end_frame=60,
    ):
        return create_animated_particle_grid(
            name,
            rows=rows,
            columns=columns,
            spacing=spacing,
            amplitude=amplitude,
            particle_radius=particle_radius,
            color=color,
            start_frame=start_frame,
            end_frame=end_frame,
        )

    def create_unicode_text(
        self,
        name,
        text,
        size=0.5,
        tracking=1,
        line_spacing=1.2,
        align="LEFT",
        color="#FFFFFF",
        location=(0, 0, 0),
        font_path=None,
        _allow_roots=None,
    ):
        return create_unicode_text(
            name,
            text=text,
            size=size,
            tracking=tracking,
            line_spacing=line_spacing,
            align=align,
            color=color,
            location=location,
            font_path=font_path,
            allow_roots=_allow_roots or [],
        )

    def create_shaped_text_plane(
        self,
        name,
        png_path,
        width=3.0,
        location=(0, 0, 0),
        _allow_roots=None,
    ):
        return create_shaped_text_plane(
            name,
            png_path=png_path,
            width=width,
            location=location,
            allow_roots=_allow_roots or [],
        )
