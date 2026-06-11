from __future__ import annotations

from paper_pipeline.config import AppConfig, ConversionConfig, PrivacyConfig
from paper_pipeline.pipeline import _grobid_upload_allowed, _is_local_url


def test_grobid_local_urls_are_allowed_by_default():
    assert _is_local_url("http://localhost:8070")
    assert _is_local_url("http://127.0.0.1:8070")


def test_grobid_external_url_requires_explicit_pdf_upload_permission():
    blocked = AppConfig(
        conversion=ConversionConfig(
            use_grobid=True,
            grobid_url="https://grobid.example.org",
        )
    )
    allowed = AppConfig(
        conversion=ConversionConfig(
            use_grobid=True,
            grobid_url="https://grobid.example.org",
        ),
        privacy=PrivacyConfig(allow_external_pdf_upload=True),
    )

    assert not _grobid_upload_allowed(blocked)
    assert _grobid_upload_allowed(allowed)
