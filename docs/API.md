# Elliott Wave Analyzer API Documentation

## Overview

The Elliott Wave Analyzer API provides endpoints for fetching stock price data and performing Elliott Wave pattern analysis. The API is built with FastAPI and provides automatic documentation via Swagger UI.

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: `https://your-domain.com/api`

## Authentication

Currently, no authentication is required for the API endpoints. Rate limiting may be applied in production environments.

## Content Type

All API requests and responses use `application/json` content type.

## Endpoints

### Health Check

Check the API health status.

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2023-12-01T12:00:00.000Z"
}
```

**Status Codes**:
- `200 OK`: API is healthy and operational

---

### Get Price Data

Retrieve historical OHLCV price data for a stock symbol.

**Endpoint**: `GET /prices/{ticker}`

**Path Parameters**:
- `ticker` (string, required): Stock ticker symbol (e.g., "AAPL", "TSLA", "SPY")

**Query Parameters**:
- `tf` (string, optional): Timeframe interval
  - Default: `"daily"`
  - Options: `"daily"`, `"4H"`, `"1H"`
- `range` (string, optional): Historical data range
  - Default: `"5y"`
  - Options: `"1y"`, `"2y"`, `"5y"`, `"10y"`

**Example Request**:
```http
GET /prices/AAPL?tf=daily&range=2y
```

**Response**:
```json
[
  {
    "timestamp": "2023-01-01T00:00:00",
    "open": 130.28,
    "high": 133.41,
    "low": 129.89,
    "close": 131.86,
    "volume": 70790813
  },
  {
    "timestamp": "2023-01-02T00:00:00", 
    "open": 131.99,
    "high": 132.14,
    "low": 125.71,
    "close": 126.04,
    "volume": 104956008
  }
]
```

**Status Codes**:
- `200 OK`: Successfully retrieved price data
- `400 Bad Request`: Invalid ticker symbol or parameters
- `404 Not Found`: No data available for the specified ticker

**Error Response**:
```json
{
  "detail": "Error fetching data: No data found for ticker INVALID"
}
```

---

### Analyze Elliott Waves

Perform Elliott Wave pattern analysis on a stock's price data.

**Endpoint**: `POST /analyze`

**Request Body**:
```json
{
  "ticker": "AAPL",
  "timeframe": "daily",
  "range": "5y",
  "zigzag_pct": 4.0
}
```

**Request Parameters**:
- `ticker` (string, required): Stock ticker symbol
- `timeframe` (string, optional): Data timeframe
  - Default: `"daily"`
  - Options: `"daily"`, `"4H"`
- `range` (string, optional): Historical data range
  - Default: `"5y"`
  - Options: `"1y"`, `"2y"`, `"5y"`, `"10y"`
- `zigzag_pct` (float, optional): ZigZag pivot threshold percentage
  - Default: 4.0 for daily, 2.0 for 4H
  - Range: 1.0 - 10.0

**Response**:
```json
{
  "primary": {
    "labels": [
      {
        "index": 125,
        "wave": "1"
      },
      {
        "index": 145,
        "wave": "2" 
      },
      {
        "index": 178,
        "wave": "3"
      }
    ],
    "fib_retracements": [
      {
        "level": 0.236,
        "price": 142.35,
        "label": "23.6% Retracement"
      },
      {
        "level": 0.382,
        "price": 138.92,
        "label": "38.2% Retracement"
      },
      {
        "level": 0.618,
        "price": 132.18,
        "label": "61.8% Retracement"
      }
    ],
    "fib_extensions": [
      {
        "level": 1.618,
        "price": 165.84,
        "label": "161.8% Extension"
      },
      {
        "level": 2.618,
        "price": 189.45,
        "label": "261.8% Extension"
      }
    ],
    "invalidation": {
      "price": 124.67,
      "reason": "Invalidation below 124.67 (Wave 1 high)"
    },
    "score": 78.5,
    "summary": "5-wave upward impulse structure detected with Wave 5 at 156.23. Strong Fibonacci conformance supports this count. Score: 78.5/100."
  },
  "alternate": {
    "labels": [
      {
        "index": 125,
        "wave": "A"
      },
      {
        "index": 145, 
        "wave": "B"
      },
      {
        "index": 178,
        "wave": "C"
      }
    ],
    "fib_retracements": [],
    "fib_extensions": [],
    "invalidation": {
      "price": 118.45,
      "reason": "Invalidation below 118.45 (Wave A start)"
    },
    "score": 54.2,
    "summary": "3-wave upward corrective ABC structure with Wave C at 156.23. Irregular corrective proportions. Score: 54.2/100."
  },
  "pivots": [
    {
      "index": 125,
      "price": 124.67,
      "timestamp": "2023-08-15T00:00:00",
      "direction": "low"
    },
    {
      "index": 145,
      "price": 147.92,
      "timestamp": "2023-09-12T00:00:00", 
      "direction": "high"
    },
    {
      "index": 178,
      "price": 132.18,
      "timestamp": "2023-10-25T00:00:00",
      "direction": "low"
    }
  ]
}
```

**Response Fields**:

**Primary/Alternate Wave Count**:
- `labels`: Array of wave labels with index positions and wave names
- `fib_retracements`: Array of Fibonacci retracement levels
- `fib_extensions`: Array of Fibonacci extension levels
- `invalidation`: Price level and reason for pattern invalidation
- `score`: Confidence score (0-100) based on Elliott Wave rules
- `summary`: Human-readable analysis summary

**Pivots**:
- `index`: Index position in the price data array
- `price`: Price level of the pivot point
- `timestamp`: ISO timestamp of the pivot
- `direction`: "high" or "low" indicating pivot type

**Status Codes**:
- `200 OK`: Successfully analyzed wave patterns
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: No data found for analysis
- `422 Unprocessable Entity`: Request validation failed

**Error Response**:
```json
{
  "detail": "Analysis failed: Insufficient data for wave analysis"
}
```

## Response Data Types

### PriceData
```typescript
interface PriceData {
  timestamp: string;      // ISO timestamp
  open: number;          // Opening price
  high: number;          // High price
  low: number;           // Low price
  close: number;         // Closing price
  volume: number;        // Trading volume
}
```

### WaveLabel
```typescript
interface WaveLabel {
  index: number;         // Index position in data
  wave: string;          // Wave identifier (1,2,3,4,5,A,B,C)
}
```

### FibLevel
```typescript
interface FibLevel {
  level: number;         // Fibonacci ratio (0.618, 1.618, etc.)
  price: number;         // Price level
  label: string;         // Descriptive label
}
```

### InvalidationLevel
```typescript
interface InvalidationLevel {
  price: number;         // Invalidation price level
  reason: string;        // Reason for invalidation
}
```

### Pivot
```typescript
interface Pivot {
  index: number;         // Index position
  price: number;         // Pivot price
  timestamp: string;     // ISO timestamp
  direction: "high" | "low";  // Pivot direction
}
```

## Error Handling

The API uses standard HTTP status codes and returns error details in JSON format:

```json
{
  "detail": "Error description here"
}
```

Common error scenarios:
- **Invalid Ticker**: Returns 400 with message about ticker not found
- **Network Issues**: Returns 400 with network-related error message
- **Insufficient Data**: Returns 400 when not enough data for analysis
- **Validation Errors**: Returns 422 with field-specific validation messages

## Rate Limiting

Current implementation does not enforce rate limiting, but production deployments should consider:

- **yfinance API limits**: Respect Yahoo Finance usage policies
- **Cache utilization**: 6-hour cache reduces API calls
- **Request throttling**: Implement rate limiting for high-traffic scenarios

## Caching

The API implements intelligent caching:

- **Cache Duration**: 6 hours for price data
- **Cache Key**: Based on ticker, timeframe, and range
- **Storage**: SQLite database for development, Redis recommended for production
- **Cache Headers**: Future versions may include HTTP cache headers

## Interactive Documentation

When the API is running, visit `/docs` for interactive Swagger UI documentation where you can:

- Test endpoints directly in the browser
- View detailed request/response schemas
- Download OpenAPI specification
- Generate client code

Alternative documentation formats:
- **ReDoc**: Available at `/redoc`
- **OpenAPI JSON**: Available at `/openapi.json`

## SDK and Client Libraries

Currently, no official SDKs are provided, but the API is compatible with:

- **JavaScript/TypeScript**: Use fetch or axios
- **Python**: Use requests or httpx
- **curl**: Standard HTTP client for testing

Example usage in JavaScript:
```javascript
// Fetch price data
const prices = await fetch('/api/prices/AAPL?tf=daily&range=1y')
  .then(res => res.json());

// Analyze waves
const analysis = await fetch('/api/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    ticker: 'AAPL',
    timeframe: 'daily',
    range: '1y',
    zigzag_pct: 4.0
  })
}).then(res => res.json());
```

## Version History

- **v1.0.0**: Initial API release with basic wave analysis
- **v1.0.1**: Added caching and error handling improvements
- **v1.1.0**: Enhanced Fibonacci calculations and scoring

## Support

For API-related questions:
- Check this documentation first
- Review interactive docs at `/docs`
- Submit issues on GitHub
- Join community discussions