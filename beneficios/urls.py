from django.urls import path
from . import views
from . import views_extra
from . import views_portal
from . import views_admin_merchants
from . import views_admin_reports
from . import views_admin_incidents
from . import views_admin_parameters
from . import views_interface
from . import views_activity, views_restoration, views_support, views_users, views_notifications

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('ingresar/', views.ingresar, name='ingresar'),
    path('crear-usuario/', views_users.crear_usuario, name='crear_usuario'),
    path('crear-usuario/completado/', views_users.registro_completado, name='registro_completado'),
    path('salir/', views.salir, name='salir'),
    path('saldo/', views.saldo, name='saldo'),
    path('movimientos/', views.movimientos, name='movimientos'),
    path('cuenta/clave/', views.cambiar_clave, name='cambiar_clave'),
    path('cuenta/actividad/', views_activity.actividad_cuenta, name='actividad_cuenta'),
    path('cuenta/sesiones/', views_portal.sesiones_abiertas, name='sesiones_abiertas'),
    path('cuenta/apariencia/', views_interface.apariencia, name='apariencia'),
    path('api/movimientos/<int:movement_id>/detalle/', views_interface.detalle_movimiento, name='detalle_movimiento'),
    path('cuenta/sesiones/cerrar-otras/', views_portal.cerrar_otras_sesiones, name='cerrar_otras_sesiones'),
    path('notificaciones/', views_notifications.notificaciones, name='notificaciones'),
    path('notificaciones/leer-todas/', views_notifications.notificaciones_leer_todas, name='notificaciones_leer_todas'),
    path('notificaciones/<int:notification_id>/leer/', views_notifications.notificacion_leer, name='notificacion_leer'),
    path('reportes/', views_support.reportar_problema, name='reportar_problema'),
    path('seguimiento/', views.seguimiento, name='seguimiento'),
    path('seguimiento/bitacora/', views.bitacora, name='bitacora'),
    path('seguimiento/parametros/', views_admin_parameters.admin_parametros, name='admin_parametros'),
    path('seguimiento/comercios/', views_admin_merchants.admin_comercios, name='admin_comercios'),
    path('seguimiento/comercios/crear/', views_admin_merchants.admin_comercio_crear, name='admin_comercio_crear'),
    path('seguimiento/comercios/<int:merchant_id>/', views_admin_merchants.admin_comercio, name='admin_comercio'),
    path('seguimiento/informes/', views_admin_reports.admin_informes, name='admin_informes'),
    path('seguimiento/informes/csv/', views_admin_reports.admin_informes_exportar, name='admin_informes_exportar'),
    path('seguimiento/movimientos/hoy/', views_portal.movimientos_admin_hoy, name='movimientos_admin_hoy'),
    path('seguimiento/usuarios/', views_users.admin_usuarios, name='admin_usuarios'),
    path('seguimiento/usuarios/crear/', views_users.admin_crear_usuario, name='admin_crear_usuario'),
    path('seguimiento/usuarios/<int:user_id>/', views_users.admin_usuario, name='admin_usuario'),
    path('seguimiento/exportar/', views.seguimiento_exportar, name='seguimiento_exportar'),
    path('seguimiento/servicios/', views.servicios, name='servicios'),
    path('seguimiento/interrupciones/<int:interruption_id>/verificar/',
         views_restoration.interrupcion_verificar, name='interrupcion_verificar'),
    path('seguimiento/reportes/', views_support.reportes_admin, name='reportes_admin'),
    path('seguimiento/incidencias/<uuid:report_id>/', views_admin_incidents.incidencia_admin,
         name='incidencia_admin'),
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
    path('pagar/comprobante/<uuid:payment_id>/pdf/', views_extra.comprobante, {'download': True},
         name='comprobante_pdf'),
    path('perfil/', views_extra.perfil, name='perfil'),
    path('tarjeta/', views_extra.tarjeta, name='tarjeta'),
    path('ayuda/', views_extra.ayuda, name='ayuda'),
]
