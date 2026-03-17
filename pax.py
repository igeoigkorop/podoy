import requests
import base64
import random
import time
import logging
from seleniumbase import SB

# ==================== PRODUCTION-READY CONFIG & LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ==================== CONFIG ====================
CHANNEL_NAME = base64.b64decode("YnJ1dGFsbGVz").decode("utf-8")  # "brutalles"
URL = f"https://www.twitch.tv/{CHANNEL_NAME}"

# Proxy support (set to "user:pass@ip:port" or None)
PROXY = None

# ==================== GEO SPOOFING (fetched once) ====================
def get_geo_data() -> dict:
    """Fetch real geo data with retry + fallback."""
    for attempt in range(3):
        try:
            resp = requests.get("http://ip-api.com/json/", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "success":
                logger.info(f"Geo locked: {data['country']} | {data['timezone']} | {data['lat']},{data['lon']}")
                return data
        except Exception as e:
            logger.warning(f"Geo fetch attempt {attempt+1} failed: {e}")
            time.sleep(2)
    # Fallback (neutral location)
    logger.warning("Using fallback geo (UTC / 0,0)")
    return {"lat": 0.0, "lon": 0.0, "timezone": "UTC", "countryCode": "US"}

geo = get_geo_data()
LAT = geo["lat"]
LON = geo["lon"]
TZ = geo["timezone"]

# ==================== MAIN LOOP ====================
while True:
    try:
        with SB(
            uc=True,                    # Undetected mode
            locale="en",
            ad_block=True,
            chromium_arg="--disable-webgl",
            proxy=PROXY,
            # headless=False,           # Uncomment if you want visible browser
        ) as sb:
            watch_time = random.randint(450, 800)  # 7.5–13.3 minutes

            logger.info(f"New session started. Target watch time: {watch_time}s")

            # ====================== CDP MODE (stealth geo + timezone) ======================
            sb.activate_cdp_mode(URL, tzone=TZ, geoloc=(LAT, LON))
            sb.sleep(2)

            # Cookie consent
            if sb.is_element_present('button:contains("Accept")'):
                sb.cdp.click('button:contains("Accept")', timeout=5)
                logger.info("Clicked cookie consent")

            sb.sleep(12)

            # "Start Watching" button (Twitch sometimes shows it)
            if sb.is_element_present('button:contains("Start Watching")'):
                sb.cdp.click('button:contains("Start Watching")', timeout=5)
                sb.sleep(8)
                logger.info("Clicked 'Start Watching'")

            # Extra consent check
            if sb.is_element_present('button:contains("Accept")'):
                sb.cdp.click('button:contains("Accept")', timeout=5)

            # ====================== LIVE CHECK ======================
            if sb.is_element_present("#live-channel-stream-information"):
                logger.info("✅ STREAM IS LIVE → Starting second viewer instance")

                # Second parallel viewer (exactly as in your original logic)
                sb2 = sb.get_new_driver(undetectable=True)
                sb2.activate_cdp_mode(URL, tzone=TZ, geoloc=(LAT, LON))
                sb2.sleep(10)

                if sb2.is_element_present('button:contains("Start Watching")'):
                    sb2.cdp.click('button:contains("Start Watching")', timeout=5)
                    sb2.sleep(8)

                if sb2.is_element_present('button:contains("Accept")'):
                    sb2.cdp.click('button:contains("Accept")', timeout=5)

                # Both viewers watch for the random duration
                sb.sleep(watch_time)
                logger.info(f"✅ Watched {watch_time}s with 2 instances")

                # ====================== CLEAN SHUTDOWN OF EXTRA DRIVER ======================
                try:
                    sb2.quit()                  # Official way per SeleniumBase docs
                    logger.info("Second viewer closed cleanly")
                except Exception as e:
                    logger.warning(f"Could not close sb2: {e} (harmless)")

            else:
                logger.info("❌ Stream is OFFLINE → Exiting script")
                break  # Exit the whole program when stream ends

    except Exception as e:
        logger.error(f"Session crashed: {e}")
        logger.info("Waiting 30s before retry...")
        time.sleep(30)
        continue  # Restart browser on any failure (network, detection, etc.)

logger.info("Script finished.")
