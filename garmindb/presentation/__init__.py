"""Presentation layer: output formatters for different targets."""

from .base import Presenter
from .markdown import MarkdownPresenter

__all__ = ["Presenter", "MarkdownPresenter"]
