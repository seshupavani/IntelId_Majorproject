from concurrent.futures import ThreadPoolExecutor
import logging

from backend.services.weather import get_weather
from backend.services.maps import get_eta
from backend.services.aqi import get_aqi
from backend.services.news import get_news, NEWS_API_CONFIGURED

logger = logging.getLogger(__name__)

def get_context(source, destination):
    if not source or not destination:
        raise ValueError("Both source and destination are required")
    
    with ThreadPoolExecutor(max_workers=4) as pool:
        weather_future = pool.submit(get_weather, destination)
        eta_future = pool.submit(get_eta, source, destination)
        aqi_future = pool.submit(get_aqi, destination)
        news_future = None
        if NEWS_API_CONFIGURED:
            news_future = pool.submit(get_news, destination)
        
        # Handle exceptions gracefully
        weather = None
        eta = None
        aqi = None
        news = None
        
        try:
            weather = weather_future.result()
        except Exception as e:
            logger.warning(f"Weather fetch failed: {e}")
            weather = {"condition": "Unknown", "temperature": None}
            
        try:
            eta = eta_future.result()
        except Exception as e:
            logger.warning(f"ETA fetch failed: {e}")
            eta = {"duration": None, "distance": None}
            
        try:
            aqi = aqi_future.result()
        except Exception as e:
            logger.warning(f"AQI fetch failed: {e}")
            aqi = {"aqi": None, "category": None}

        if news_future is not None:
            try:
                news = news_future.result()
            except Exception as e:
                logger.warning(f"News fetch failed: {e}")
                news = None

    return {
        "weather": weather,
        "eta": eta,
        "aqi": aqi,
        "news": news,
    }
