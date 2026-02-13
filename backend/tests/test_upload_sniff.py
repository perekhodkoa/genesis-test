import json

import pandas as pd
import pytest

from app.middleware.error_handler import ValidationError
from app.services.upload_service import (
    _parse_json,
    _unwrap_json_object,
    _flatten_geojson,
    sniff_data,
    _sanitize_column_name,
    _clean_dataframe,
)


# --- CSV-style sniff ---

class TestSniffData:
    def test_basic_sniff(self):
        """sniff_data produces correct schema for a simple DataFrame."""
        df = pd.DataFrame({
            "Name": ["Alice", "Bob", "Carol"],
            "Age": [30, 25, 35],
            "Score": [9.5, 8.0, 7.5],
        })
        result = sniff_data(df)

        assert result["row_count"] == 3
        assert result["recommended_db"] == "postgres"
        assert len(result["columns"]) == 3

        col_names = [c["name"] for c in result["columns"]]
        assert "name" in col_names
        assert "age" in col_names
        assert "score" in col_names

    def test_sniff_detects_types(self):
        """sniff_data detects integer, float, string types."""
        df = pd.DataFrame({"count": [1, 2], "price": [1.5, 2.5], "label": ["a", "b"]})
        result = sniff_data(df)
        types = {c["name"]: c["dtype"] for c in result["columns"]}
        assert types["count"] == "integer"
        assert types["price"] == "float"
        assert types["label"] == "string"

    def test_sniff_sample_rows(self):
        """sniff_data returns sample rows capped at SNIFF_ROWS."""
        df = pd.DataFrame({"x": list(range(100))})
        result = sniff_data(df)
        assert len(result["sample_rows"]) == 5  # SNIFF_ROWS = 5
        assert result["row_count"] == 100

    def test_sniff_nullable(self):
        """sniff_data detects nullable columns."""
        df = pd.DataFrame({"a": [1, None, 3], "b": [1, 2, 3]})
        result = sniff_data(df)
        cols = {c["name"]: c["nullable"] for c in result["columns"]}
        assert cols["a"] is True
        assert cols["b"] is False


# --- JSON parsing ---

class TestParseJson:
    def test_plain_array(self):
        """A top-level array of objects is parsed directly."""
        data = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        df = _parse_json(json.dumps(data).encode())
        assert len(df) == 2
        assert list(df.columns) == ["a", "b"]

    def test_empty_array_raises(self):
        """An empty array raises ValidationError."""
        with pytest.raises(ValidationError, match="no records"):
            _parse_json(b"[]")

    def test_scalar_raises(self):
        """A bare scalar JSON value raises ValidationError."""
        with pytest.raises(ValidationError):
            _parse_json(b'"just a string"')


# --- Unwrap JSON object ---

class TestUnwrapJsonObject:
    def test_well_known_key_data(self):
        """Unwraps via well-known 'data' key."""
        obj = {"data": [{"id": 1}, {"id": 2}], "meta": "ignored"}
        assert _unwrap_json_object(obj) == [{"id": 1}, {"id": 2}]

    def test_well_known_key_results(self):
        """Unwraps via well-known 'results' key."""
        obj = {"results": [{"x": 10}]}
        assert _unwrap_json_object(obj) == [{"x": 10}]

    def test_well_known_key_features(self):
        """Unwraps via well-known 'features' key (GeoJSON)."""
        obj = {"type": "FeatureCollection", "features": [{"type": "Feature"}]}
        assert _unwrap_json_object(obj) == [{"type": "Feature"}]

    def test_auto_detect_single_array(self):
        """When no well-known key matches, detects the single array-of-dicts field."""
        obj = {"myCustomData": [{"a": 1}, {"a": 2}], "version": "1.0"}
        assert _unwrap_json_object(obj) == [{"a": 1}, {"a": 2}]

    def test_fallback_single_record(self):
        """When no array field found, wraps the whole object as one record."""
        obj = {"name": "solo", "value": 42}
        assert _unwrap_json_object(obj) == [{"name": "solo", "value": 42}]

    def test_ambiguous_multiple_arrays(self):
        """When multiple array fields exist and none are well-known, fallback to single record."""
        obj = {"arr1": [{"a": 1}], "arr2": [{"b": 2}]}
        result = _unwrap_json_object(obj)
        assert result == [obj]


# --- GeoJSON flattening ---

class TestFlattenGeojson:
    def test_geojson_features(self):
        """GeoJSON features are flattened: properties to top level, geometry extracted."""
        features = [
            {
                "type": "Feature",
                "properties": {"name": "Point A", "value": 10},
                "geometry": {"type": "Point", "coordinates": [1.0, 2.0]},
            },
            {
                "type": "Feature",
                "properties": {"name": "Point B", "value": 20},
                "geometry": {"type": "Point", "coordinates": [3.0, 4.0]},
            },
        ]
        result = _flatten_geojson(features)
        assert len(result) == 2
        assert result[0]["name"] == "Point A"
        assert result[0]["geometry_type"] == "Point"
        assert "coordinates" not in result[0]  # coordinates should be in geometry_coordinates
        assert result[0]["geometry_coordinates"] == json.dumps([1.0, 2.0])
        # 'type' and 'properties' should not be top-level
        assert "type" not in result[0]
        assert "properties" not in result[0]

    def test_non_geojson_passthrough(self):
        """Non-GeoJSON items are returned unchanged."""
        items = [{"a": 1}, {"a": 2}]
        assert _flatten_geojson(items) is items

    def test_empty_list(self):
        """Empty list passes through."""
        assert _flatten_geojson([]) == []


# --- Helpers ---

class TestSanitizeColumnName:
    def test_basic(self):
        assert _sanitize_column_name("My Column!") == "my_column_"

    def test_leading_digit(self):
        assert _sanitize_column_name("1st_place") == "col_1st_place"

    def test_empty(self):
        assert _sanitize_column_name("   ") == "unnamed"


class TestCleanDataframe:
    def test_strips_whitespace(self):
        df = pd.DataFrame({"val": [" hello ", " world "]})
        cleaned = _clean_dataframe(df.copy())
        assert cleaned["val"].tolist() == ["hello", "world"]

    def test_coerces_numeric_strings(self):
        df = pd.DataFrame({"num": [" 10 ", "20", "30"]})
        cleaned = _clean_dataframe(df.copy())
        assert cleaned["num"].dtype.kind in ("i", "f")  # int or float

    def test_keeps_non_numeric_strings(self):
        df = pd.DataFrame({"text": ["abc", "def", "ghi"]})
        cleaned = _clean_dataframe(df.copy())
        assert cleaned["text"].dtype == object
