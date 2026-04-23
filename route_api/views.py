import uuid
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import RouteRequestSerializer
from .services.fuel_optimizer import optimize_route

# In-memory map cache (map_id → html string). Fine for a demo.
_map_cache: dict = {}


class RouteView(APIView):
    def post(self, request):
        serializer = RouteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        start = serializer.validated_data['start']
        finish = serializer.validated_data['finish']

        try:
            result = optimize_route(start, finish)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response(
                {'error': f'Unexpected error: {str(exc)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Store map HTML for the /api/map/<id>/ endpoint
        map_id = str(uuid.uuid4())
        _map_cache[map_id] = result.pop('map_html')
        result['map_url'] = request.build_absolute_uri(f'/api/map/{map_id}/')

        return Response(result, status=status.HTTP_200_OK)


class MapView(APIView):
    def get(self, request, route_id):
        html = _map_cache.get(route_id)
        if html is None:
            return Response({'error': 'Map not found or expired.'}, status=status.HTTP_404_NOT_FOUND)
        return HttpResponse(html, content_type='text/html')
