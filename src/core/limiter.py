

from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.config import settings


limiter = Limiter(
    key_func=get_remote_address, 
    storage_uri=settings.redis_dsn, 
    strategy="moving-window"
)