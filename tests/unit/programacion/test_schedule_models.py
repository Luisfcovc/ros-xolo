from datetime import date, datetime, timezone
import pytest
from django.core.exceptions import ValidationError
from ros_xolo.programacion.models.drafts import PeriodoProgramacion


def test_period_rejects_inverted_dates():
    period = PeriodoProgramacion(date_from=date(2026, 9, 21), date_to=date(2026, 9, 14))
    with pytest.raises(ValidationError): period.clean()
