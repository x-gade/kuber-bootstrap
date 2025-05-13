# utils/logger.py

def log(text, level="info"):
    color = {
        "info": "\033[94m",    # Синий
        "warn": "\033[93m",    # Желтый
        "error": "\033[91m",   # Красный
        "ok": "\033[92m"       # Зеленый
    }.get(level, "\033[0m")
    print(f"{color}[{level.upper()}] {text}\033[0m")
