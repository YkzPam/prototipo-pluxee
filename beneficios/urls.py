from django.urls import path
from . import views
from . import views_extra
from . import views_activity, views_restoration, views_support

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('ingresar/', views.ingresar, name='ingresar'),
    path('salir/', views.salir, name='salir'),
    path('saldo/', views.saldo, name='saldo'),
    path('movimientos/', views.movimientos, name='movimientos'),
    path('cuenta/clave/', views.cambiar_clave, name='cambiar_clave'),
    path('cuenta/actividad/', views_activity.actividad_cuenta, name='actividad_cuenta'),
    path('reportes/', views_support.reportar_problema, name='reportar_problema'),
    path('seguimiento/', views.seguimiento, name='seguimiento'),
    path('seguimiento/exportar/', views.seguimiento_exportar, name='seguimiento_exportar'),
    path('seguimiento/servicios/', views.servicios, name='servicios'),
    path('seguimiento/interrupciones/<int:interruption_id>/verificar/',
         views_restoration.interrupcion_verificar, name='interrupcion_verificar'),
    path('seguimiento/reportes/', views_support.reportes_admin, name='reportes_admin'),
    path('seguimiento/reportes/<uuid:report_id>/', views_support.reportes_admin_actualizar,
         name='reportes_admin_actualizar'),
    path('api/cuentas/<int:account_id>/saldo/', views.api_saldo, name='api_saldo'),
    path('api/cuentas/<int:account_id>/movimientos/', views.api_movimientos, name='api_movimientos'),
    path('api/consultas/estado/', views.estado_consultas, name='estado_consultas'),
    path('api/sesion/actividad/', views.actividad, name='actividad'),
]

urlpatterns += [
    path('comercios/', views_extra.comercios, name='comercios'),
    path('comercios/<int:merchant_id>/favorito/', views_extra.favorito, name='favorito'),
    path('pagar/', views_extra.pagar, name='pagar'),
    path('pagar/clave-dinamica/', views_extra.generar_clave_dinamica, name='generar_clave_dinamica'),
    path('pagar/comprobante/<uuid:payment_id>/', views_extra.comprobante, name='comprobante'),
    path('perfil/', views_extra.perfil, name='perfil'),
    path('tarjeta/', views_extra.tarjeta, name='tarjeta'),
    path('ayuda/', views_extra.ayuda, name='ayuda'),
]
