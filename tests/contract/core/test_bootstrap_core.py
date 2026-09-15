import pytest

from ros_xolo.core.services.catalog_changes import CoreValidationError, validate_manifest


def test_manifest_requires_schema_version_one():
    with pytest.raises(CoreValidationError):
        validate_manifest({"schema_version": 2})
