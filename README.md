# Elliott Wave Analyzer

A comprehensive web application for Elliott Wave pattern analysis with automatic wave counting, Fibonacci level calculations, and educational insights.

![Elliott Wave Analyzer](https://via.placeholder.com/800x400/0f1419/58a6ff?text=Elliott+Wave+Analyzer)

## 🚀 Features

### Core Functionality
- **Automatic Elliott Wave Detection**: Rule-based enumeration of 5-wave impulse and ABC corrective patterns
- **ZigZag Pivot Detection**: Configurable percentage-based swing detection (4% daily, 2% intraday default)
- **Fibonacci Analysis**: Automatic retracement and extension level calculations
- **Dual Wave Counts**: Primary and alternate pattern interpretations with confidence scoring
- **Real-time Data**: Live stock data via yfinance with intelligent caching
- **Interactive Charts**: Candlestick charts with wave labels, Fibonacci levels, and invalidation lines

### Technical Features
- **Smart Caching**: 6-hour SQLite cache for price data to minimize API calls
- **Confidence Scoring**: 0-100 scoring system based on Elliott Wave rule compliance and Fibonacci ratios
- **Export Functionality**: JSON reports with full analysis data
- **Responsive Design**: Dark-themed UI optimized for financial analysis
- **Educational Focus**: Built-in disclaimers and educational context

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend      │    │   Data Source   │
│   (React)       │◄──►│   (FastAPI)     │◄──►│   (yfinance)    │
│                 │    │                 │    │                 │
│ • Controls      │    │ • Wave Analysis │    │ • Yahoo Finance │
│ • Charts        │    │ • Fibonacci     │    │ • OHLCV Data    │
│ • Results       │    │ • Caching       │    │ • Real-time     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Tech Stack
- **Backend**: Python 3.11, FastAPI, SQLite, pandas, numpy
- **Frontend**: React 18, Vite, Recharts, Axios
- **Analysis**: Custom Elliott Wave algorithms with Fibonacci calculations
- **Infrastructure**: Docker, Docker Compose, GitHub Actions
- **Testing**: pytest (backend), Playwright (frontend)

## 📋 Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (for containerized deployment)

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

```bash
git clone <repository-url>
cd EWA
cp infra/.env.example infra/.env
docker-compose -f infra/docker-compose.yml up --build
```

Access the application at `http://localhost:3000`

### Option 2: Development Setup

#### Backend Setup
```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# Unix/MacOS
source venv/bin/activate

pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

The application will be available at:
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`

## 🎯 Usage Guide

### Basic Analysis
1. **Enter Stock Symbol**: Input any valid ticker (e.g., AAPL, TSLA, SPY)
2. **Select Timeframe**: Choose between Daily or 4H intervals
3. **Set Date Range**: Pick from 1y, 2y, 5y, or 10y historical data
4. **Adjust ZigZag**: Fine-tune pivot sensitivity (1-10%)
5. **Analyze**: Click "Analyze Waves" to process the data

### Interpreting Results
- **Primary/Alternate Tabs**: Compare different wave interpretations
- **Confidence Score**: 0-100 rating based on Elliott Wave rules
- **Wave Labels**: Numbered/lettered labels on chart pivots
- **Fibonacci Levels**: Retracement and extension lines
- **Invalidation**: Red dashed line showing pattern breakdown level

### Chart Controls
- **Toggle Fibonacci**: Show/hide retracement and extension levels
- **Toggle Invalidation**: Show/hide invalidation levels
- **Toggle Pivots**: Show/hide ZigZag pivot points
- **Primary/Alternate**: Switch between wave count interpretations

## 🔬 Analysis Algorithm

### ZigZag Detection
```python
# Percentage-based pivot detection
def detect_zigzag(df, pct_threshold=4.0):
    # Identifies significant highs and lows
    # Default: 4% for daily, 2% for intraday
```

### Wave Enumeration
```python
# Elliott Wave rule validation
impulse_rules = [
    "Wave 2 never retraces more than 100% of Wave 1",
    "Wave 3 is never the shortest wave", 
    "Wave 4 does not overlap Wave 1 price territory"
]

corrective_rules = [
    "Wave B typically retraces 38-78% of Wave A",
    "Wave C often equals Wave A or 1.618x Wave A"
]
```

### Fibonacci Analysis
- **Retracements**: 23.6%, 38.2%, 50%, 61.8%, 78.6%
- **Extensions**: 100%, 127.2%, 161.8%, 200%, 261.8%
- **Confluence Detection**: Identifies overlapping levels within 2% tolerance

### Scoring System
```
Score = 100 - (
    w1 * mean_fibonacci_error +
    w2 * overlap_penalties +
    w3 * channel_deviation +
    w4 * shortest_wave_penalty
)
```

## 📊 API Reference

### Endpoints

#### GET `/prices/{ticker}`
Retrieve OHLCV price data for analysis.

**Parameters:**
- `ticker` (path): Stock symbol (e.g., AAPL)
- `tf` (query): Timeframe - "daily" or "4H"
- `range` (query): Date range - "1y", "2y", "5y", "10y"

**Response:**
```json
[
  {
    "timestamp": "2023-01-01T00:00:00",
    "open": 100.0,
    "high": 105.0,
    "low": 95.0,
    "close": 102.0,
    "volume": 1000000
  }
]
```

#### POST `/analyze`
Perform Elliott Wave analysis on price data.

**Request Body:**
```json
{
  "ticker": "AAPL",
  "timeframe": "daily",
  "range": "5y",
  "zigzag_pct": 4.0
}
```

**Response:**
```json
{
  "primary": {
    "labels": [{"index": 0, "wave": "1"}],
    "fib_retracements": [{"level": 0.618, "price": 150.0, "label": "61.8% Retracement"}],
    "fib_extensions": [{"level": 1.618, "price": 180.0, "label": "161.8% Extension"}],
    "invalidation": {"price": 140.0, "reason": "Wave 1 low breach"},
    "score": 75.0,
    "summary": "5-wave upward impulse detected..."
  },
  "alternate": {...},
  "pivots": [{"index": 0, "price": 100.0, "timestamp": "2023-01-01", "direction": "low"}]
}
```

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest --cov=analysis --cov-report=html
```

**Test Coverage:**
- ZigZag pivot detection accuracy
- Elliott Wave rule validation  
- Fibonacci calculation precision
- API endpoint integration
- Error handling and edge cases

### Frontend Tests
```bash
cd frontend
npm run test
```

**Test Scenarios:**
- User interaction flows
- Chart rendering and updates
- API integration
- Export functionality

## 📦 Deployment

### Production Docker Build
```bash
docker build -t elliott-wave-backend ./backend
docker build -t elliott-wave-frontend ./frontend
```

### Environment Variables
```bash
# Backend
PYTHONPATH=/app
API_HOST=0.0.0.0
API_PORT=8000
CACHE_TTL_HOURS=6

# Optional: OpenAI integration
OPENAI_API_KEY=your-key-here

# Frontend
VITE_API_BASE_URL=http://localhost:8000
```

### Scaling Considerations
- **Caching**: Implement Redis for distributed caching
- **Rate Limiting**: Add request throttling for yfinance calls
- **CDN**: Serve static assets via CDN
- **Load Balancing**: Use nginx for multiple backend instances

## 🔧 Configuration

### ZigZag Thresholds
```python
# Default thresholds by timeframe
ZIGZAG_DEFAULTS = {
    "daily": 4.0,    # 4% for daily charts
    "4H": 2.0,       # 2% for 4-hour charts  
    "1H": 1.5        # 1.5% for hourly charts
}
```

### Fibonacci Ratios
```python
# Customizable Fibonacci levels
RETRACEMENTS = [0.236, 0.382, 0.5, 0.618, 0.786]
EXTENSIONS = [1.0, 1.272, 1.618, 2.0, 2.618]
```

### Wave Scoring Weights
```python
SCORING_WEIGHTS = {
    "fibonacci_error": 0.4,
    "overlap_penalty": 0.3,
    "channel_deviation": 0.2,
    "shortest_wave_penalty": 0.1
}
```

## 🐛 Troubleshooting

### Common Issues

**Backend won't start:**
```bash
# Check Python version
python --version  # Should be 3.11+

# Install dependencies
pip install -r requirements.txt

# Check port availability  
netstat -an | findstr 8000
```

**Frontend build fails:**
```bash
# Clear npm cache
npm cache clean --force

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install
```

**No data returned:**
- Verify ticker symbol is valid on Yahoo Finance
- Check internet connection for yfinance API
- Ensure date range has sufficient data
- Try different ZigZag threshold values

**Analysis scores are low:**
- Increase date range for more data
- Adjust ZigZag percentage threshold
- Verify the symbol has trending price action
- Check if data contains sufficient pivots

## 📚 Elliott Wave Theory Background

### Core Principles
1. **Impulse Waves**: 5-wave motive patterns (1-2-3-4-5)
2. **Corrective Waves**: 3-wave counter-trend patterns (A-B-C)
3. **Fibonacci Relationships**: Mathematical ratios in wave proportions
4. **Alternation**: Wave 2 and 4 typically differ in character
5. **Channeling**: Waves often respect trend channel boundaries

### Rules vs Guidelines
**Rules (Must Never Be Violated):**
- Wave 2 cannot retrace more than 100% of Wave 1
- Wave 3 cannot be the shortest wave
- Wave 4 cannot overlap Wave 1 price territory

**Guidelines (Often But Not Always True):**
- Wave 3 often extends 1.618x Wave 1
- Wave 2 typically retraces 50-61.8% of Wave 1
- Wave 4 usually retraces 38.2% of Wave 3

## 📄 License & Disclaimer

### Educational Use Only
This tool is designed for **educational and illustrative purposes only**. Elliott Wave analysis is highly subjective and should **never be used as the sole basis for investment decisions**.

### Risk Disclaimer
- **Not Financial Advice**: All analysis provided is for educational purposes
- **Subjective Analysis**: Elliott Wave patterns are open to interpretation
- **Market Risk**: Trading and investing involve substantial risk of loss
- **No Guarantees**: Past performance does not guarantee future results

### Data Sources
- Price data provided by Yahoo Finance via yfinance library
- Real-time data may be delayed 15-20 minutes
- Historical data accuracy depends on data provider

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`pytest` for backend, `npm test` for frontend)
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

### Development Guidelines
- Follow PEP 8 for Python code
- Use TypeScript for new frontend components
- Add tests for new functionality
- Update documentation for API changes
- Ensure Docker builds succeed

## 📞 Support

- **Issues**: GitHub Issues tracker
- **Discussions**: GitHub Discussions for questions
- **Documentation**: Check `/docs` folder for detailed guides
- **API Docs**: Visit `/docs` endpoint when backend is running

## 🎯 Roadmap

### Version 1.1
- [ ] Real-time WebSocket price updates
- [ ] Additional timeframes (1H, 15M, 5M)
- [ ] Wave degree labeling (Primary, Intermediate, Minor)
- [ ] Pattern confidence intervals

### Version 1.2  
- [ ] Multiple symbol comparison
- [ ] Portfolio-level wave analysis
- [ ] Custom Fibonacci ratio configuration
- [ ] Advanced channeling detection

### Version 2.0
- [ ] Machine learning wave recognition
- [ ] Options chain integration
- [ ] Social sentiment analysis
- [ ] Professional analyst tools

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Author

**m-zayed5722**
- GitHub: [@m-zayed5722](https://github.com/m-zayed5722)
- Email: mzayed5722@gmail.com
- Repository: [elliott-wave-analyzer](https://github.com/m-zayed5722/elliott-wave-analyzer)

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/m-zayed5722/elliott-wave-analyzer/issues).

## ⭐ Show Your Support

Give a ⭐ if this project helped you learn about Elliott Wave analysis!

## 📈 Live Demo

Deploy to Streamlit Cloud using this repository for instant access!

---

**Created with ❤️ for the Elliott Wave trading community**

**⚠️ Disclaimer**: This tool is for educational purposes only. Elliott Wave analysis is subjective and should not be considered as financial advice. Always do your own research and consult with financial professionals before making investment decisions.