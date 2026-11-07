"""Factory Method: respuestas uniformes sin exponer detalles internos."""
from abc import ABC, abstractmethod
from django.http import JsonResponse


class ResponseCreator(ABC):
    @abstractmethod
    def create_response(self, request, message, **extra):
        raise NotImplementedError


class UpdatedResponseCreator(ResponseCreator):
    def create_response(self, request, message='Consulta actualizada.', **extra):
        return JsonResponse({'status': 'updated', 'message': message,
                             'request_id': str(request.request_id), **extra})


class PendingResponseCreator(ResponseCreator):
    def create_response(self, request, message='La consulta está pendiente. El servicio de prueba no está disponible; se puede reintentar.', **extra):
        return JsonResponse({'status': 'pending', 'message': message,
                             'request_id': str(request.request_id), **extra}, status=503)


class RejectedResponseCreator(ResponseCreator):
    def create_response(self, request, message='No se permite acceder a esta información.', **extra):
        status_code = extra.pop('http_status', 403)
        status = extra.pop('status', 'error')
        return JsonResponse({'status': status, 'message': message,
                             'request_id': str(request.request_id), **extra}, status=status_code)
