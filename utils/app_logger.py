from config import APP_ENV


def debug_print(*args, **kwargs):
    """
    Custom print function that only prints if the application
    environment (APP_ENV) is set to 'dev'.
    """
    if APP_ENV == "dev":
        print(*args, **kwargs)
