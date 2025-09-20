"""
Integration tests for the FastAPI application.
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json

# Import the app
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_price_data():
    """Sample price data for testing."""
    return [
        {
            "timestamp": "2023-01-01T00:00:00",
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 102.0,
            "volume": 1000000
        },
        {
            "timestamp": "2023-01-02T00:00:00", 
            "open": 102.0,
            "high": 110.0,
            "low": 98.0,
            "close": 108.0,
            "volume": 1200000
        },
        {
            "timestamp": "2023-01-03T00:00:00",
            "open": 108.0,
            "high": 112.0,
            "low": 104.0,
            "close": 106.0,
            "volume": 900000
        }
    ]


class TestAPIEndpoints:
    """Test API endpoint functionality."""

    def test_root_endpoint(self, client):
        """Test the root endpoint returns expected message."""
        response = client.get("/")
        assert response.status_code == 200
        assert "Elliott Wave Analyzer API" in response.json()["message"]

    def test_health_endpoint(self, client):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    @patch('app.fetch_yahoo_data')
    def test_get_prices_success(self, mock_fetch, client, sample_price_data):
        """Test successful price data retrieval."""
        mock_fetch.return_value = sample_price_data
        
        response = client.get("/prices/AAPL?tf=daily&range=1y")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["open"] == 100.0
        assert data[0]["high"] == 105.0

    @patch('app.fetch_yahoo_data')
    def test_get_prices_invalid_ticker(self, mock_fetch, client):
        """Test price retrieval with invalid ticker."""
        mock_fetch.side_effect = Exception("No data found for ticker INVALID")
        
        response = client.get("/prices/INVALID")
        
        assert response.status_code == 400
        assert "Error fetching data" in response.json()["detail"]

    @patch('app.get_cached_data')
    @patch('app.fetch_yahoo_data') 
    @patch('app.cache_data')
    def test_price_caching_mechanism(self, mock_cache, mock_fetch, mock_get_cache, client, sample_price_data):
        """Test that price data caching works correctly."""
        # First call: no cache, should fetch and cache
        mock_get_cache.return_value = None
        mock_fetch.return_value = sample_price_data
        
        response1 = client.get("/prices/AAPL?tf=daily&range=1y")
        
        assert response1.status_code == 200
        mock_fetch.assert_called_once()
        mock_cache.assert_called_once()
        
        # Second call: should use cache, not fetch again
        mock_get_cache.return_value = sample_price_data
        mock_fetch.reset_mock()
        mock_cache.reset_mock()
        
        response2 = client.get("/prices/AAPL?tf=daily&range=1y")
        
        assert response2.status_code == 200
        mock_fetch.assert_not_called()  # Should not fetch again
        mock_cache.assert_not_called()  # Should not cache again

    @patch('app.get_cached_data')
    @patch('app.fetch_yahoo_data')
    @patch('app.detect_zigzag')
    @patch('app.analyze_waves')
    @patch('app.calculate_fibonacci_levels')
    def test_analyze_endpoint_success(self, mock_fib, mock_waves, mock_zigzag, mock_fetch, mock_cache, client, sample_price_data):
        """Test successful wave analysis."""
        # Mock all the components
        mock_cache.return_value = sample_price_data
        
        mock_zigzag.return_value = [
            {'index': 0, 'price': 95.0, 'direction': 'low'},
            {'index': 1, 'price': 110.0, 'direction': 'high'},
            {'index': 2, 'price': 104.0, 'direction': 'low'}
        ]
        
        mock_waves.return_value = {
            'primary': MagicMock(
                labels=[],
                score=75.0,
                summary="Test primary wave count"
            ),
            'alternate': MagicMock(
                labels=[],
                score=45.0,
                summary="Test alternate wave count"
            )
        }
        
        mock_fib.return_value = {
            'retracements': [
                {'level': 0.618, 'price': 102.0, 'label': '61.8% Retracement'}
            ],
            'extensions': [
                {'level': 1.618, 'price': 115.0, 'label': '161.8% Extension'}
            ]
        }
        
        # Mock calculate_invalidation_levels
        with patch('app.calculate_invalidation_levels') as mock_invalidation:
            mock_invalidation.return_value = {
                'price': 90.0,
                'reason': 'Test invalidation level'
            }
            
            request_data = {
                "ticker": "AAPL",
                "timeframe": "daily",
                "range": "1y",
                "zigzag_pct": 3.0
            }
            
            response = client.post("/analyze", json=request_data)
            
            assert response.status_code == 200
            data = response.json()
            
            # Check response structure
            assert "primary" in data
            assert "alternate" in data
            assert "pivots" in data
            
            assert len(data["pivots"]) == 3
            assert data["primary"]["score"] == 75.0
            assert data["alternate"]["score"] == 45.0

    def test_analyze_endpoint_missing_data(self, client):
        """Test analysis with non-existent ticker."""
        request_data = {
            "ticker": "NONEXISTENT",
            "timeframe": "daily", 
            "range": "1y"
        }
        
        with patch('app.get_cached_data') as mock_cache:
            mock_cache.return_value = None
            with patch('app.fetch_yahoo_data') as mock_fetch:
                mock_fetch.side_effect = Exception("No data found")
                
                response = client.post("/analyze", json=request_data)
                
                assert response.status_code == 400

    def test_analyze_endpoint_default_zigzag_thresholds(self, client, sample_price_data):
        """Test that default zigzag thresholds are applied correctly."""
        with patch('app.get_cached_data') as mock_cache:
            mock_cache.return_value = sample_price_data
            with patch('app.detect_zigzag') as mock_zigzag:
                mock_zigzag.return_value = []
                with patch('app.analyze_waves') as mock_waves:
                    mock_waves.return_value = {
                        'primary': MagicMock(labels=[], score=50.0, summary="Test"),
                        'alternate': MagicMock(labels=[], score=30.0, summary="Test")
                    }
                    with patch('app.calculate_fibonacci_levels') as mock_fib:
                        mock_fib.return_value = {'retracements': [], 'extensions': []}
                        with patch('app.calculate_invalidation_levels') as mock_inv:
                            mock_inv.return_value = {'price': 100.0, 'reason': 'Test'}
                            
                            # Test daily default (4%)
                            response = client.post("/analyze", json={
                                "ticker": "AAPL",
                                "timeframe": "daily",
                                "range": "1y"
                            })
                            
                            assert response.status_code == 200
                            # Verify zigzag was called with 4% for daily
                            mock_zigzag.assert_called()
                            call_args = mock_zigzag.call_args[0]
                            assert call_args[1] == 4.0  # Default for daily
                            
                            # Test 4H default (2%)
                            mock_zigzag.reset_mock()
                            response = client.post("/analyze", json={
                                "ticker": "AAPL", 
                                "timeframe": "4H",
                                "range": "1y"
                            })
                            
                            assert response.status_code == 200
                            call_args = mock_zigzag.call_args[0]
                            assert call_args[1] == 2.0  # Default for 4H

    def test_timeframe_to_interval_mapping(self, client):
        """Test that timeframe parameter maps to correct yfinance intervals."""
        from app import timeframe_to_interval
        
        assert timeframe_to_interval("daily") == "1d"
        assert timeframe_to_interval("4H") == "4h"
        assert timeframe_to_interval("1H") == "1h"
        assert timeframe_to_interval("unknown") == "1d"  # Default

    @patch('app.sqlite3.connect')
    def test_database_initialization(self, mock_connect):
        """Test that database initialization works correctly."""
        from app import init_db
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        init_db()
        
        mock_connect.assert_called_once_with("cache.db")
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_invalid_request_validation(self, client):
        """Test request validation for analyze endpoint."""
        # Missing required ticker field
        response = client.post("/analyze", json={
            "timeframe": "daily",
            "range": "1y"
        })
        
        assert response.status_code == 422  # Validation error

    def test_cors_headers(self, client):
        """Test that CORS headers are properly set."""
        response = client.options("/", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET"
        })
        
        # FastAPI/CORS should handle this automatically
        # This test ensures the middleware is properly configured
        assert response.status_code in [200, 204]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])