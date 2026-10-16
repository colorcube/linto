import pytest
import numpy as np
from plotter_studio.core.document import Document, ImportItem, VectorPath, LogicalPen
from plotter_studio.core.geometry import AffineTransform
from plotter_studio.pipeline.compiler import (
    PipelineConfig, compile_document_to_plot_job
)


def test_compile_basic_document():
    doc = Document()
    # Add two items with different pens
    path1 = VectorPath(
        points=np.array([[10.0, 10.0], [50.0, 10.0]]),
        pen_id=1,
    )
    path2 = VectorPath(
        points=np.array([[20.0, 20.0], [60.0, 20.0]]),
        pen_id=2,
    )
    item = ImportItem(name="Test", paths=[path1, path2])
    doc.items.append(item)

    cfg = PipelineConfig(sort_paths=True)
    job = compile_document_to_plot_job(doc, cfg)

    assert len(job.layers) == 2
    assert 1 in job.layers
    assert 2 in job.layers
    assert abs(job.total_draw_mm - 80.0) < 1e-4
    assert job.pen_changes == 1
    assert job.estimated_duration_s > 0.0
    assert len(job.steps) >= 2


def test_compile_pen_disabled_and_remapping():
    doc = Document()
    path1 = VectorPath(points=np.array([[0.0, 0.0], [10.0, 0.0]]), pen_id=1)
    path2 = VectorPath(points=np.array([[0.0, 5.0], [10.0, 5.0]]), pen_id=2)
    doc.items.append(ImportItem(name="Item", paths=[path1, path2]))

    # Disable pen 2
    pen2 = doc.get_pen(2)
    assert pen2 is not None
    pen2.enabled = False

    job = compile_document_to_plot_job(doc)
    assert len(job.layers) == 1
    assert 1 in job.layers
    assert 2 not in job.layers

    # Enable pen 2, remap all to pen 1
    pen2.enabled = True
    doc.remap_all_to_pen(1)

    job_mono = compile_document_to_plot_job(doc)
    assert len(job_mono.layers) == 1
    assert 1 in job_mono.layers
    # Both lines now in layer 1
    assert len(job_mono.layers[1].lines) == 2


def test_compile_overhang_warning_and_clipping():
    doc = Document()
    doc.page.apply_preset("A4", "portrait")
    pb = doc.page.plottable_box

    # Create path that extends 20mm beyond right border
    overhang_x = pb.max_x + 20.0
    path = VectorPath(points=np.array([[pb.min_x + 10, pb.min_y + 10], [overhang_x, pb.min_y + 10]]), pen_id=1)
    doc.items.append(ImportItem(name="Big", paths=[path]))

    # Without clipping: warning present
    job_unclipped = compile_document_to_plot_job(doc, PipelineConfig(clip_to_plottable=False))
    assert len(job_unclipped.warnings) == 1
    assert "Zeichnung ragt um 20.0 mm über den plottbaren Bereich hinaus" in job_unclipped.warnings[0]
    assert abs(job_unclipped.layers[1].lines[0][-1, 0] - overhang_x) < 1e-4

    # With clipping: clipped to pb.max_x
    job_clipped = compile_document_to_plot_job(doc, PipelineConfig(clip_to_plottable=True))
    clipped_line = job_clipped.layers[1].lines[0]
    assert abs(clipped_line[-1, 0] - pb.max_x) < 1e-4


def test_compile_dynamic_flatten_tolerance_and_scaling():
    from plotter_studio.core.svg_import import load_svg

    svg_sample = """<svg width="100mm" height="100mm" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <path d="M 10 50 C 20 5, 80 5, 90 50" stroke="#000000" fill="none"/>
    </svg>"""
    item = load_svg(svg_sample, name="Curve")
    doc = Document()
    doc.items.append(item)

    # Coarse flattening vs fine flattening (with simplify disabled to measure raw subdivision)
    job_coarse = compile_document_to_plot_job(
        doc, PipelineConfig(flatten_tolerance_mm=0.5, simplify_tolerance_mm=0.0)
    )
    job_fine = compile_document_to_plot_job(
        doc, PipelineConfig(flatten_tolerance_mm=0.01, simplify_tolerance_mm=0.0)
    )
    assert job_fine.total_points > job_coarse.total_points

    # Scaling the item up by 5x increases the physical curve size and thus produces more subdivisions
    item.transform = AffineTransform.scale(5.0)
    job_scaled = compile_document_to_plot_job(
        doc, PipelineConfig(flatten_tolerance_mm=0.05, simplify_tolerance_mm=0.0)
    )
    item.transform = AffineTransform.identity()
    job_unscaled = compile_document_to_plot_job(
        doc, PipelineConfig(flatten_tolerance_mm=0.05, simplify_tolerance_mm=0.0)
    )
    assert job_scaled.total_points > job_unscaled.total_points

