# Elliott Wave Analyzer - Streamlit Deployment Guide

## 🚀 Local Deployment

### Prerequisites
- Python 3.11+
- pip package manager

### Quick Start
```bash
# Clone the repository
git clone <your-repo-url>
cd EWA

# Install dependencies
pip install -r requirements-streamlit.txt

# Run the application
streamlit run streamlit_app.py
```

The app will be available at: **http://localhost:8501**

---

## ☁️ Cloud Deployment Options

### 1. Streamlit Community Cloud (FREE)

**Steps:**
1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub account
4. Select your repository
5. Set main file as `streamlit_app.py`
6. Deploy!

**Requirements file:** `requirements-streamlit.txt`

**Pros:**
- ✅ Completely free
- ✅ Easy one-click deployment
- ✅ Automatic updates from GitHub
- ✅ HTTPS included

**Cons:**
- ❌ Limited resources (1GB RAM)
- ❌ Apps sleep when inactive
- ❌ Public by default

### 2. Heroku Deployment

**Create these files:**

`Procfile`:
```
web: streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0
```

`setup.sh`:
```bash
mkdir -p ~/.streamlit/

echo "\
[general]\n\
email = \"your-email@domain.com\"\n\
" > ~/.streamlit/credentials.toml

echo "\
[server]\n\
headless = true\n\
enableCORS=false\n\
port = $PORT\n\
" > ~/.streamlit/config.toml
```

**Deploy:**
```bash
# Install Heroku CLI
# Login and create app
heroku create your-elliott-wave-app
heroku buildpacks:set heroku/python
git push heroku main
```

**Pros:**
- ✅ Professional hosting
- ✅ Custom domains
- ✅ Always-on (paid plans)

**Cons:**
- ❌ No free tier anymore
- ❌ More complex setup

### 3. Railway Deployment

**railway.toml**:
```toml
[build]
builder = "nixpacks"

[deploy]
healthcheckPath = "/"
healthcheckTimeout = 100
restartPolicyType = "always"

[env]
PORT = "8501"
```

**Deploy:**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

**Pros:**
- ✅ Simple deployment
- ✅ Good free tier
- ✅ Modern platform

### 4. Render Deployment

**render.yaml**:
```yaml
services:
  - type: web
    name: elliott-wave-analyzer
    env: python
    buildCommand: "pip install -r requirements-streamlit.txt"
    startCommand: "streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0"
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.7
```

**Pros:**
- ✅ Generous free tier
- ✅ Automatic HTTPS
- ✅ Git integration

---

## 🐳 Docker Deployment

### Dockerfile for Streamlit
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements-streamlit.txt .
RUN pip install --no-cache-dir -r requirements-streamlit.txt

# Copy application files
COPY . .

# Expose port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Run streamlit
ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Docker Compose
```yaml
version: '3.8'
services:
  elliott-wave-analyzer:
    build: .
    ports:
      - "8501:8501"
    environment:
      - STREAMLIT_SERVER_HEADLESS=true
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

**Build and run:**
```bash
docker build -t elliott-wave-analyzer .
docker run -p 8501:8501 elliott-wave-analyzer
```

---

## 🌐 Advanced Deployment (AWS/GCP/Azure)

### AWS EC2 + ECS
1. Create ECR repository
2. Push Docker image
3. Create ECS cluster
4. Deploy as service with ALB

### Google Cloud Run
```bash
gcloud run deploy elliott-wave-analyzer \
  --image gcr.io/PROJECT-ID/elliott-wave-analyzer \
  --platform managed \
  --region us-central1 \
  --port 8501
```

### Azure Container Instances
```bash
az container create \
  --resource-group myResourceGroup \
  --name elliott-wave-analyzer \
  --image your-registry/elliott-wave-analyzer \
  --ports 8501 \
  --dns-name-label elliott-wave-unique
```

---

## 📁 File Structure for Deployment

```
EWA/
├── streamlit_app.py              # Main Streamlit application
├── requirements-streamlit.txt     # Dependencies
├── backend/                      # Analysis modules
│   └── analysis/
│       ├── __init__.py
│       ├── zigzag.py
│       ├── waves.py
│       └── fib.py
├── .streamlit/                   # Streamlit config (optional)
│   └── config.toml
├── Dockerfile                    # Docker configuration
├── docker-compose.yml           # Docker Compose
├── Procfile                     # Heroku
├── railway.toml                 # Railway
├── render.yaml                  # Render
└── README.md                    # Documentation
```

---

## 🔧 Configuration Options

### .streamlit/config.toml
```toml
[global]
dataFrameSerialization = "legacy"

[server]
headless = true
runOnSave = true
port = 8501

[browser]
gatherUsageStats = false
serverAddress = "localhost"

[theme]
primaryColor = "#1f77b4"
backgroundColor = "#0e1117"
secondaryBackgroundColor = "#262730"
textColor = "#fafafa"
```

### Environment Variables
- `STREAMLIT_SERVER_PORT`: Server port (default: 8501)
- `STREAMLIT_SERVER_HEADLESS`: Run without browser (true/false)
- `STREAMLIT_BROWSER_GATHER_USAGE_STATS`: Disable telemetry (false)

---

## 📊 Performance Optimization

### Caching Strategies
```python
# Data caching
@st.cache_data(ttl=3600)  # 1 hour cache
def fetch_stock_data(ticker, timeframe, range_period):
    # Implementation

# Resource caching
@st.cache_resource
def init_analysis_engine():
    # Heavy initialization
```

### Memory Management
```python
# Clear cache periodically
if st.button("Clear Cache"):
    st.cache_data.clear()
    st.cache_resource.clear()
```

### Database Optimization
- Use SQLite for local caching
- Consider PostgreSQL for production
- Implement connection pooling for high traffic

---

## 🔒 Security Considerations

### Production Settings
```python
# Disable debug mode
st.set_page_config(
    layout="wide",
    initial_sidebar_state="expanded"
)

# Input validation
def validate_ticker(ticker):
    import re
    return bool(re.match(r'^[A-Z]{1,5}$', ticker))
```

### Environment Variables
```bash
# Don't commit these to git
YAHOO_FINANCE_API_KEY=your_key_here
DATABASE_URL=postgresql://...
SECRET_KEY=your_secret_key
```

---

## 📈 Monitoring and Analytics

### Health Checks
```python
# Add health check endpoint
def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}
```

### Usage Analytics
```python
# Track usage (privacy compliant)
def log_analysis_request(ticker, timeframe):
    # Implementation
```

### Error Monitoring
```python
import logging
logging.basicConfig(level=logging.INFO)

try:
    # Analysis code
except Exception as e:
    logging.error(f"Analysis failed: {e}")
    st.error("Analysis failed. Please try again.")
```

---

## 🚨 Troubleshooting

### Common Issues

**Import Errors:**
```bash
# Check Python path
export PYTHONPATH="${PYTHONPATH}:/path/to/your/backend"
```

**Port Conflicts:**
```bash
# Use different port
streamlit run streamlit_app.py --server.port 8502
```

**Memory Issues:**
```python
# Reduce data size
df = df.tail(1000)  # Last 1000 rows only
```

**Slow Loading:**
```python
# Add progress bars
progress_bar = st.progress(0)
for i in range(100):
    # Processing
    progress_bar.progress(i + 1)
```

---

## 📚 Additional Resources

- **Streamlit Documentation**: https://docs.streamlit.io
- **Plotly Charting**: https://plotly.com/python
- **Yahoo Finance API**: https://pypi.org/project/yfinance
- **Elliott Wave Theory**: Educational resources and books

---

## 🎯 Next Steps

1. **Choose deployment platform** (Streamlit Cloud recommended for beginners)
2. **Set up repository** on GitHub
3. **Configure domain** (optional)
4. **Set up monitoring** for production use
5. **Add authentication** if needed
6. **Scale resources** based on usage

Happy deploying! 🚀