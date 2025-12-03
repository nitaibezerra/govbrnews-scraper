"""
Tests for UploadToCogfyManager, specifically the datetime UTC conversion.
"""
import os
import sys
import pytest
import pandas as pd
from datetime import datetime, date, timezone, timedelta

# Add src directory to path to resolve relative imports in upload_to_cogfy_manager
src_path = os.path.join(os.path.dirname(__file__), '..', 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from upload_to_cogfy_manager import UploadToCogfyManager


class TestFormatDatetimeForCogfy:
    """Tests for the _format_datetime_for_cogfy static method."""

    def test_timestamp_with_brasilia_timezone_converts_to_utc(self):
        """
        Test that a timestamp with Brasília timezone (UTC-3) is correctly converted to UTC.

        Example:
        - Input: 2025-11-17 19:24:43 (Brasília, UTC-3)
        - Expected output: "2025-11-17T22:24:43Z" (UTC)
        """
        brasilia_tz = timezone(timedelta(hours=-3))
        timestamp = pd.Timestamp(
            year=2025, month=11, day=17,
            hour=19, minute=24, second=43,
            tz=brasilia_tz
        )

        result = UploadToCogfyManager._format_datetime_for_cogfy(timestamp)

        # 19:24:43 in Brasília (UTC-3) = 22:24:43 in UTC
        assert result == "2025-11-17T22:24:43Z"

    def test_timestamp_with_utc_timezone_stays_same(self):
        """
        Test that a timestamp already in UTC stays the same.
        """
        timestamp = pd.Timestamp(
            year=2025, month=11, day=17,
            hour=22, minute=24, second=43,
            tz='UTC'
        )

        result = UploadToCogfyManager._format_datetime_for_cogfy(timestamp)

        assert result == "2025-11-17T22:24:43Z"

    def test_naive_timestamp_passes_through(self):
        """
        Test that a naive timestamp (no timezone) passes through as-is.

        Note: Naive timestamps are assumed to already be in the correct timezone
        for the context where they're used.
        """
        timestamp = pd.Timestamp(
            year=2025, month=11, day=17,
            hour=19, minute=24, second=43
        )

        result = UploadToCogfyManager._format_datetime_for_cogfy(timestamp)

        # Naive timestamp is formatted as-is
        assert result == "2025-11-17T19:24:43Z"

    def test_date_object_uses_noon(self):
        """
        Test that a date object (without time) uses noon (12:00:00).
        """
        date_value = date(2025, 11, 17)

        result = UploadToCogfyManager._format_datetime_for_cogfy(date_value)

        assert result == "2025-11-17T12:00:00Z"

    def test_timestamp_with_positive_offset_converts_correctly(self):
        """
        Test that a timestamp with positive UTC offset converts correctly.

        Example: Tokyo time (UTC+9)
        - Input: 2025-11-17 19:24:43 (Tokyo, UTC+9)
        - Expected output: "2025-11-17T10:24:43Z" (UTC)
        """
        tokyo_tz = timezone(timedelta(hours=9))
        timestamp = pd.Timestamp(
            year=2025, month=11, day=17,
            hour=19, minute=24, second=43,
            tz=tokyo_tz
        )

        result = UploadToCogfyManager._format_datetime_for_cogfy(timestamp)

        # 19:24:43 in Tokyo (UTC+9) = 10:24:43 in UTC
        assert result == "2025-11-17T10:24:43Z"

    def test_timestamp_crossing_midnight_converts_correctly(self):
        """
        Test that conversion works correctly when it crosses midnight.

        Example:
        - Input: 2025-11-17 01:30:00 (Brasília, UTC-3)
        - Expected output: "2025-11-17T04:30:00Z" (UTC, same day)

        - Input: 2025-11-17 22:30:00 (Brasília, UTC-3)
        - Expected output: "2025-11-18T01:30:00Z" (UTC, next day)
        """
        brasilia_tz = timezone(timedelta(hours=-3))

        # Early morning - stays same day
        early_timestamp = pd.Timestamp(
            year=2025, month=11, day=17,
            hour=1, minute=30, second=0,
            tz=brasilia_tz
        )
        result_early = UploadToCogfyManager._format_datetime_for_cogfy(early_timestamp)
        assert result_early == "2025-11-17T04:30:00Z"

        # Late night - crosses to next day
        late_timestamp = pd.Timestamp(
            year=2025, month=11, day=17,
            hour=22, minute=30, second=0,
            tz=brasilia_tz
        )
        result_late = UploadToCogfyManager._format_datetime_for_cogfy(late_timestamp)
        assert result_late == "2025-11-18T01:30:00Z"

    def test_invalid_type_raises_error(self):
        """
        Test that an unsupported type raises ValueError.
        """
        with pytest.raises(ValueError, match="Unsupported datetime type"):
            UploadToCogfyManager._format_datetime_for_cogfy("2025-11-17")

        with pytest.raises(ValueError, match="Unsupported datetime type"):
            UploadToCogfyManager._format_datetime_for_cogfy(123456789)
