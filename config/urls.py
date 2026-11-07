from django.urls import include, path

urlpatterns = [path('', include('beneficios.urls'))]
handler403 = 'beneficios.views.permission_error'
handler404 = 'beneficios.views.not_found'
handler500 = 'beneficios.views.server_error'
