import sys
from loguru import logger

logger.remove()


LOG_FORMAT_MODERATE = (
    '{time:YYYY-MM-DD HH:mm:ss} | '
    '<level>{level:<8}</level> | '
    '{name}:{function}:{line} - '
    '{message}'
)


logger.add(sys.stdout, format=LOG_FORMAT_MODERATE, colorize=True)


logger.add(
    'logs/info.log',
    format='{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} - {message}',
    level='INFO',
    colorize=False,
    rotation='10 MB',  
    retention='10 days', 
    compression='zip',  
)


logger.add(
    'logs/errors.log',
    format='{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} - {message}',
    level='ERROR',
    colorize=False,
    rotation='10 MB',
    retention='30 days', 
    compression='zip',
)