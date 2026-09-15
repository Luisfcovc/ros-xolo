import pytest

from ros_xolo.core.services.locking import WriteBusy, organization_lock


@pytest.mark.django_db(transaction=True)
def test_missing_organization_does_not_acquire_lock():
    with pytest.raises(WriteBusy):
        with organization_lock("00000000-0000-0000-0000-000000000000"):
            pass
