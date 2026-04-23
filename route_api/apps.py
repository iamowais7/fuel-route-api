from django.apps import AppConfig


class RouteApiConfig(AppConfig):
    name = 'route_api'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from .services.station_loader import preload_stations
        preload_stations()
