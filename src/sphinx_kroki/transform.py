"""Transform Kroki nodes into standard docutils image nodes."""

from __future__ import annotations

from os.path import relpath
from pathlib import Path
from typing import TYPE_CHECKING, cast

from docutils.nodes import SkipNode, image
from sphinx.locale import __
from sphinx.transforms import SphinxTransform

from .kroki import KrokiError, KrokiNode, render_kroki
from .util import logger

if TYPE_CHECKING:
    from sphinx.builders import Builder


class KrokiToImageTransform(SphinxTransform):
    """Render Kroki nodes into image nodes during the read phase."""

    default_priority = 10

    @property
    def _builder(self) -> Builder:
        return self.app.builder

    def apply(self, **_kwargs: object) -> None:
        """Replace each Kroki node in the document with an image node."""
        source = str(Path(self.document["source"]).parent)
        for node in self.document.findall(KrokiNode):
            img = image()
            img["kroki"] = node
            img["alt"] = node["source"]
            img["classes"] = list(node.get("classes", []))
            if "align" in node:
                img["align"] = node["align"]

            out = self._render(node)
            img["uri"] = relpath(out, source)

            node.replace_self(img)

    def _render(self, node: KrokiNode, prefix: str = "kroki") -> Path:
        output_format = cast("str", node["format"])
        diagram_type = cast("str", node["type"])
        diagram_source = cast("str", node["source"])

        try:
            out = render_kroki(self._builder, node, output_format, prefix)
        except KrokiError as exc:
            logger.warning(
                __("kroki %s diagram (%s) with source %r: %s"),
                diagram_type,
                output_format,
                diagram_source,
                exc,
            )
            raise SkipNode from exc

        return out
