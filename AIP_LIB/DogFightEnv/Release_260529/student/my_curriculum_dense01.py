# -*- coding: utf-8 -*-
"""Curriculum variant: dense pursuit cap 0.1/step (vs 0.2 in my_curriculum).

Used as the second arm of the dense-cap comparison sweep:
  experiments/sweeps/curriculum_dense_sweep.yaml
"""
from __future__ import annotations

from student.my_curriculum import build_stages


def get_stages():
    return build_stages(dense_scale=0.1)


__all__ = ["get_stages"]
