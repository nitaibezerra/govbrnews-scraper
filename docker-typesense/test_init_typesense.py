#!/usr/bin/env python3
"""
Tests for init-typesense.py script

Run with: python -m pytest test_init_typesense.py -v
"""

import pytest
import pandas as pd
from datetime import datetime
from init_typesense import calculate_published_week


class TestCalculatePublishedWeek:
    """Tests for calculate_published_week function."""

    def test_week_1_of_2024(self):
        """Test first week of 2024."""
        # 2024-01-01 (Monday) is week 1 of 2024
        ts = int(datetime(2024, 1, 1).timestamp())
        result = calculate_published_week(ts)
        assert result == 202401

    def test_week_43_of_2025(self):
        """Test week 43 of 2025."""
        # 2025-10-23 (Thursday) is week 43 of 2025
        ts = int(datetime(2025, 10, 23).timestamp())
        result = calculate_published_week(ts)
        assert result == 202543

    def test_week_52_of_2024(self):
        """Test last week of 2024."""
        # 2024-12-23 (Monday) is week 52 of 2024
        ts = int(datetime(2024, 12, 23).timestamp())
        result = calculate_published_week(ts)
        assert result == 202452

    def test_iso_8601_year_rollover(self):
        """Test ISO 8601 year rollover (Dec 31 can be week 1 of next year)."""
        # 2024-12-30 (Monday) starts week 1 of 2025 in ISO 8601
        ts = int(datetime(2024, 12, 30).timestamp())
        result = calculate_published_week(ts)
        assert result == 202501  # Week 1 of 2025, not 2024

    def test_another_iso_rollover(self):
        """Test another ISO rollover case."""
        # 2024-12-31 (Tuesday) is also week 1 of 2025
        ts = int(datetime(2024, 12, 31).timestamp())
        result = calculate_published_week(ts)
        assert result == 202501

    def test_mid_year_week(self):
        """Test a mid-year week."""
        # 2025-06-15 (Sunday)
        ts = int(datetime(2025, 6, 15).timestamp())
        result = calculate_published_week(ts)
        # Should be week 24 of 2025
        assert result == 202524

    def test_invalid_timestamp_zero(self):
        """Test with zero timestamp."""
        result = calculate_published_week(0)
        assert result is None

    def test_invalid_timestamp_negative(self):
        """Test with negative timestamp."""
        result = calculate_published_week(-1)
        assert result is None

    def test_invalid_timestamp_nan(self):
        """Test with NaN."""
        result = calculate_published_week(float('nan'))
        assert result is None

    def test_invalid_timestamp_none(self):
        """Test with None."""
        result = calculate_published_week(None)
        assert result is None

    def test_pandas_series_application(self):
        """Test that function works with pandas Series.apply()."""
        # Create a series of timestamps
        timestamps = pd.Series([
            int(datetime(2024, 1, 1).timestamp()),
            int(datetime(2025, 10, 23).timestamp()),
            0,
            None
        ])

        # Apply function
        result = timestamps.apply(calculate_published_week)

        # Check results
        assert result.iloc[0] == 202401
        assert result.iloc[1] == 202543
        assert pd.isna(result.iloc[2])  # Zero should return None
        assert pd.isna(result.iloc[3])  # None should return None

    def test_multiple_years(self):
        """Test weeks across multiple years."""
        test_cases = [
            (datetime(2020, 1, 6), 202002),   # Week 2 of 2020
            (datetime(2021, 12, 27), 202152), # Week 52 of 2021
            (datetime(2022, 7, 18), 202229),  # Week 29 of 2022
            (datetime(2023, 3, 15), 202311),  # Week 11 of 2023
            (datetime(2024, 9, 30), 202440),  # Week 40 of 2024
        ]

        for dt, expected in test_cases:
            ts = int(dt.timestamp())
            result = calculate_published_week(ts)
            assert result == expected, f"Failed for {dt}: expected {expected}, got {result}"

    def test_format_yyyyww(self):
        """Test that result is in YYYYWW format."""
        ts = int(datetime(2025, 10, 23).timestamp())
        result = calculate_published_week(ts)

        # Check it's an integer
        assert isinstance(result, int)

        # Check format: should be 6 digits (YYYYWW)
        assert result >= 200001  # Min: year 2000, week 1
        assert result <= 299953  # Max: year 2999, week 53

        # Extract year and week
        year = result // 100
        week = result % 100

        # Check valid ranges
        assert 2000 <= year <= 2999
        assert 1 <= week <= 53


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
