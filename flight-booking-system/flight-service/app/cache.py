import redis
import os
import json
import logging

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_SENTINEL_HOSTS", "redis:6379").split(":")[0]
REDIS_PORT = int(os.getenv("REDIS_SENTINEL_HOSTS", "redis:6379").split(":")[1]) if ":" in os.getenv("REDIS_SENTINEL_HOSTS", "") else 6379

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

TTL = 300

def get_flight_cache(flight_id: str):
    key = f"flight:{flight_id}"
    data = redis_client.get(key)
    if data:
        logger.info(f"Cache HIT: {key}")
        return json.loads(data)
    logger.info(f"Cache MISS: {key}")
    return None

def set_flight_cache(flight_id: str, data: dict):
    key = f"flight:{flight_id}"
    redis_client.setex(key, TTL, json.dumps(data))
    logger.info(f"Cache SET: {key}")

def invalidate_flight(flight_id: str):
    key = f"flight:{flight_id}"
    redis_client.delete(key)
    logger.info(f"Cache INVALIDATE: {key}")

def get_search_cache(origin: str, dest: str, date: str):
    key = f"search:{origin}:{dest}:{date or 'any'}"
    data = redis_client.get(key)
    if data:
        logger.info(f"Cache HIT: {key}")
        return json.loads(data)
    logger.info(f"Cache MISS: {key}")
    return None

def set_search_cache(origin: str, dest: str, date: str, data: list):
    key = f"search:{origin}:{dest}:{date or 'any'}"
    redis_client.setex(key, TTL, json.dumps(data))
    logger.info(f"Cache SET: {key}")

def invalidate_searches():
    keys = redis_client.keys("search:*")
    if keys:
        redis_client.delete(*keys)
    logger.info("Cache INVALIDATE searches")