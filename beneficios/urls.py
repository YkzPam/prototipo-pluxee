from django.urls import path
from . import views
from . import views_extra

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('ingresar/', views.ingresar, name='ingresar'),
    path('salir/', views.salir, name='salir'),
    path('saldo/', views.saldo, name='saldo'),
    path('movimientos/', views.movimientos, name='movimientos'),
    path('cuenta/clave/', views.cambiar_clave, name='cambiar_clave'),
    path('seguimiento/', views.seguimiento, name='seguimiento'),
    path('seguimiento/servicios/', views.servicios, name='servicios'),
    path('api/cuentas/<int:account_id>/saldo/', views.api_saldo, name='api_saldo'),
    path('api/cuentas/<int:account_id>/movimientos/', views.api_movimientos, name='api_movimientos'),
    path('api/sesion/actividad/', views.actividad, name='actividad'),
]

urlpatterns += [
    path('comercios/', views_extra.comercios, name='comercios'),
    path('comercios/<int:merchant_id>/favorito/', views_extra.favorito, name='favorito'),
    path('pagar/', views_extra.pagar, name='pagar'),
    path('pagar/comprobante/<uuid:payment_id>/', views_extra.comprobante, name='comprobante'),
    path('perfil/', views_extra.perfil, name='perfil'),
    path('tarjeta/', views_extra.tarjeta, name='tarjeta'),
    path('ayuda/', views_extra.ayuda, name='ayuda'),
]
