import axios from 'axios';

const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? 'https://your-api-domain.com' 
  : 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for debugging
api.interceptors.request.use(
  (config) => {
    console.log('API Request:', config.method.toUpperCase(), config.url);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response) {
      // Server responded with error status
      const message = error.response.data?.detail || error.response.data?.message || error.message;
      throw new Error(message);
    } else if (error.request) {
      // Request made but no response received
      throw new Error('Unable to connect to the analysis server. Please check if the backend is running.');
    } else {
      // Something else happened
      throw new Error(error.message);
    }
  }
);

export const getPrices = async (ticker, timeframe = 'daily', range = '5y') => {
  try {
    const response = await api.get(`/prices/${ticker}`, {
      params: {
        tf: timeframe,
        range: range
      }
    });
    return response.data;
  } catch (error) {
    throw new Error(`Failed to fetch price data: ${error.message}`);
  }
};

export const analyzeWaves = async (params) => {
  try {
    const response = await api.post('/analyze', params);
    return response.data;
  } catch (error) {
    throw new Error(`Analysis failed: ${error.message}`);
  }
};

export const healthCheck = async () => {
  try {
    const response = await api.get('/health');
    return response.data;
  } catch (error) {
    throw new Error(`Health check failed: ${error.message}`);
  }
};

export default api;