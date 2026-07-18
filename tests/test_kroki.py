"""Test the kroki extension."""

import re
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import requests
import sphinx
from sphinx.application import Sphinx
from sphinx.testing.util import SphinxTestApp

from sphinx_kroki import kroki as kroki_module


def get_content(app: Sphinx) -> str:
    app.builder.build_all()

    index = app.outdir / "index.html"
    return index.read_text()


@pytest.mark.sphinx("html", testroot="kroki", confoverrides={"master_doc": "index"})
def test_kroki_html(app: SphinxTestApp) -> None:
    content = get_content(app)
    assert app.warning.getvalue() == ""
    html = (
        r'figure[^>]*?(?:kroki kroki-plantuml align-default)?" .*?>\s*'
        r'<img alt="bar -&gt; baz" class="kroki kroki-plantuml" .+?/>.*?'
        r'<span class="caption-text">caption of diagram</span>.*?</p>'
    )
    assert re.search(html, content, re.DOTALL)

    html = (
        r'<p>Hello <img alt="bar -&gt; baz" '
        r'class="kroki kroki-plantuml" .*?/> kroki world</p>'
    )
    assert re.search(html, content, re.DOTALL)

    html = r'<img .+?class="kroki kroki-mermaid graph" .+?/>'
    assert re.search(html, content, re.DOTALL)

    html = r'<img .+?class="kroki kroki-graphviz" .*?/>'
    assert re.search(html, content, re.DOTALL)

    html = (
        r'figure[^>]*?kroki kroki-plantuml align-center" .*?>\s*?'
        r'<img alt="foo -&gt; bar ".*?/>.*?'
        r'<span class="caption-text">on <em>center</em></span>'
    )
    assert re.search(html, content, re.DOTALL)

    if sphinx.version_info >= (9, 0):
        html = r'<img.*?class="align-right kroki kroki-ditaa".*?/>'
    else:
        html = r'<img.*?class="kroki kroki-ditaa align-right".*?/>'
    assert re.search(html, content, re.DOTALL)


@pytest.mark.sphinx(
    "html", testroot="kroki-warnings", confoverrides={"master_doc": "index"}
)
def test_kroki_invalid_directives_warn_and_suppress_output(app: SphinxTestApp) -> None:
    content = get_content(app)
    warnings = app.warning.getvalue()

    expected = (
        "Kroki directive cannot have both filename option and a filename argument",
        "Kroki directive cannot have both type option and a type argument",
        "Kroki directive cannot have both format option and a format argument",
        "Kroki directive cannot have both content and a filename argument",
        "Kroki directive has to define diagram type.",
        "Ignoring kroki directive without content",
        "Kroki directive options must be a YAML mapping",
        "not found or reading it failed",
    )
    for message in expected:
        assert message in warnings
    assert warnings.count("WARNING") == len(expected)
    assert "index.rst:4: " in warnings
    assert "<img" not in content


def test_render_kroki_cleans_up_partial_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_timeout = 30
    message = "boom"

    class ExplodingResponse:
        def raise_for_status(self) -> None:
            return None

        def iter_content(self, chunk_size: int = 1) -> Iterator[bytes]:  # noqa: ARG002
            yield b"<svg"
            raise requests.exceptions.ConnectionError(message)

    builder = cast(
        "Any",
        SimpleNamespace(
            config=SimpleNamespace(kroki_url="https://kroki.io"),
            outdir=tmp_path / "_build",
            imagedir="_images",
        ),
    )
    node = kroki_module.KrokiNode()
    node["source"] = "Alice -> Bob"
    node["type"] = "plantuml"

    def fake_post(
        _url: str, *, json: object, stream: bool, timeout: int
    ) -> ExplodingResponse:
        assert json
        assert stream is True
        assert timeout == request_timeout
        return ExplodingResponse()

    monkeypatch.setattr(kroki_module.requests, "post", fake_post)

    with pytest.raises(
        kroki_module.KrokiError, match="kroki did not produce a diagram"
    ):
        kroki_module.render_kroki(builder, node, "svg")

    image_dir = builder.outdir / builder.imagedir
    assert image_dir.exists()
    assert list(image_dir.iterdir()) == []
