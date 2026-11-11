# Comprobación del prototipo académico

Fecha de ejecución: 6 de noviembre de 2026. El ejercicio utiliza la base temporal del ejecutor de pruebas de Django y datos ficticios independientes de la demostración. No se consultó la plataforma real de Pluxee.

La suite comprueba autenticación, validación de entradas, bloqueo temporal de intentos, aislamiento entre cuentas, separación del administrador, saldo calculado desde movimientos persistidos, filtros, consultas interrumpidas, reintentos, integridad de registros, continuidad y vencimiento de sesiones, invalidación al cerrar, CSRF, política de contraseñas, escape de contenido, encabezados de protección y bitácora sin secretos. También inyecta un fallo controlado en un observador para comprobar que el resultado de la consulta no se falsifique y que el fallo de registro sea explícito.

## Hallazgo real CF01: reintento inmediato sin restricción

La primera ejecución detectó un defecto en `test_interrupted_balance_is_pending_without_zero_and_recovers_after_retry`: después de una consulta interrumpida, una nueva solicitud inmediata devolvió **503** en lugar de la respuesta **429** prevista para limitar el reintento. La ejecución inicial terminó con **31 pruebas, 30 correctas y 1 fallo**, en 6,549 segundos. El error observado fue `AssertionError: 503 != 429`.

La consulta pendiente escribía su marca temporal en la sesión, pero Django no guardaba esos cambios al emitir una respuesta 503. La corrección conserva el código HTTP de indisponibilidad y guarda expresamente la sesión antes de devolver esa respuesta controlada. La misma operación persiste la actividad reconocida de la sesión. El cambio no altera el saldo ni los movimientos.

La repetición comprobó que la primera consulta interrumpida devuelve 503, el reintento inmediato devuelve 429 con `Retry-After` y, tras restablecer el servicio y superar la espera, se recupera el saldo correcto. La comparación de los registros antes y después conserva la integridad de los movimientos. Se añadieron dos casos independientes sobre CSRF válido y fallo del registro de auditoría.

## Resultado de la repetición del alcance inicial

La ejecución del alcance inicial terminó con **33 pruebas correctas de 33**, en **8,383 segundos**, sin problemas detectados por las comprobaciones de sistema de Django. La salida completa está en `ejecucion_final.txt`. Las respuestas 400, 401, 403, 405, 429 y 503 que aparecen en ese registro corresponden a escenarios negativos esperados y comprobados por la suite.

El informe de cobertura de esta ejecución registró **445 sentencias, 15 sin ejecutar y 97 %** en los módulos de la aplicación incluidos en `cobertura_final.txt`, omitiendo pruebas y migraciones. La cifra corresponde a esa selección de código Python y a esa ejecución; no acredita cobertura del navegador, del despliegue HTTPS ni de funciones que se incorporen posteriormente.

Comandos utilizados desde la carpeta del prototipo:

```powershell
.\.venv\Scripts\python.exe -m coverage run --source=beneficios manage.py test beneficios.tests --settings=config.settings.testing -v 2
.\.venv\Scripts\python.exe -m coverage report -m --omit="beneficios/tests/*,beneficios/migrations/*"
```

Esta comprobación no sustituye una prueba de carga de diez minutos, una prueba de comprensión con participantes, una evaluación de penetración externa ni la verificación de una conexión HTTPS desplegada. No se atribuye certificación ISO ni aceptación empresarial a los resultados.

## Resultado final de la ampliación funcional

La ampliación incorpora veinte pruebas sobre pago ficticio, comprobantes, comercios, favoritos, perfil y tarjeta. La ejecución conjunta terminó con **53 pruebas correctas de 53**, en **17,520 segundos**, sin problemas detectados por las comprobaciones de sistema de Django. La salida completa está en `ejecucion_ampliada.txt`. Se conservan los registros anteriores para distinguir la revisión inicial de la versión ampliada.

La cobertura de la ejecución ampliada registró **740 sentencias, 35 sin ejecutar y 95 %**, según `cobertura_ampliada.txt`, con la misma exclusión de pruebas y migraciones. La ampliación comprueba un único débito al repetir la misma solicitud, rechazo de una referencia reutilizada con otro importe o comercio, aislamiento de comprobantes, rechazo de datos de otra cuenta enviados por formulario, montos inválidos, saldo insuficiente, PIN incorrecto, bloqueo temporal del PIN, tarjeta bloqueada e interrupciones sin cargo. También comprueba búsquedas y favoritos por usuario, edición validada del perfil y protección CSRF en las nuevas operaciones.

Una prueba adicional inyecta una infracción real de la restricción `NOT NULL` de la bitácora durante un pago ficticio. La implementación devuelve 503 y revierte conjuntamente el movimiento y el comprobante, sin informar un pago exitoso. Esta comprobación valida la corrección preventiva del aislamiento del observador mediante un punto de recuperación de la transacción y el rechazo explícito del pago cuando no puede auditarse. No se presenta como una ejecución fallida anterior a esa corrección: el caso se ejecutó con la protección ya incorporada.

Los pagos comprobados pertenecen únicamente a la base temporal de pruebas; no representan transferencias, pagos ni conexiones con Pluxee. La repetición secuencial de solicitudes acredita la idempotencia ensayada. No se ha ejecutado desde esta suite una prueba de concurrencia multihilo o de carga que permita extender esa afirmación a cualquier condición de producción.

## Verificación del paquete después de los ajustes visuales

El pipeline local `scripts/entregar.py` volvió a comprobar el proyecto después de integrar el formato común de moneda en las plantillas. La ejecución terminó con **53 pruebas correctas**, en **16,282 segundos**, y una cobertura de **95 %: 750 sentencias, 37 sin ejecutar**, según `verificacion_paquete.txt`. La comprobación de migraciones no encontró cambios pendientes y la recopilación de recursos terminó correctamente. Estas cifras corresponden al paquete revisado y conservan las exclusiones indicadas en `.coveragerc`.

El intento de carga se documenta por separado en `perfil_carga_parcial.json`: su interrupción impide acreditar la ventana completa de diez minutos y el percentil HTTP previsto. Los eventos persistidos permiten describir consultas observadas, pero no reemplazan las muestras de latencia HTTP que faltan.

## Hallazgo real CF02: contraseña restablecida sin cambio obligatorio

Fecha de revisión: 10 de noviembre de 2026. Una revisión manual del módulo «Administrar usuarios», contrastada con la pauta OWASP de la guía («Obligar el cambio de contraseñas temporales luego de su utilización»), detectó que `beneficios/views_users.py` asignaba `must_change_password = False` al restablecer una contraseña desde la ficha del usuario. Un script de comprobación con el cliente de pruebas de Django confirmó el defecto: el beneficiario ingresó con la contraseña asignada por el administrador y accedió al inicio sin que se le exigiera cambiarla. El módulo no tenía pruebas automatizadas propias.

La corrección marca la contraseña restablecida como temporal (`must_change_password = True`), conserva la invalidación de las sesiones anteriores mediante `access_revision` y registra en la bitácora «Contraseña temporal asignada.». La ficha informa al administrador que el usuario deberá cambiarla al ingresar. El cambio obligatorio lo aplica el `SessionPolicyMiddleware` que ya existía.

Se agregó `test_user_management.py` con diez pruebas: filtros del listado y exclusión de cuentas administrativas, edición validada del perfil, contraseña temporal con cambio obligatorio (redirección a `cambiar_clave`, respuesta `password_change_required` en la API y acceso normal tras el cambio), rechazo de contraseñas débiles o distintas, desactivación con confirmación e invalidación de sesiones, abono idempotente, rechazo de acciones desconocidas, bloqueo del beneficiario en todas las rutas de administración y redirección del usuario anónimo al ingreso.

| Medición | Antes de las pruebas nuevas | Después |
|---|---|---|
| Pruebas ejecutadas | 110 correctas | **120 correctas de 120** |
| Cobertura de `views_users.py` | 46 % | **84 %** |
| Cobertura de `forms_users.py` | 93 % | **100 %** |
| Cobertura total (`.coveragerc`) | 80 % | **83 %: 2.221 sentencias, 386 sin ejecutar** |

La salida completa está en `ejecucion_gestion_usuarios.txt` y la cobertura en `cobertura_gestion_usuarios.txt`.

Actualización posterior (10 de noviembre de 2026): al separar el panel de Seguimiento de la Bitácora y mostrar el concepto y el monto en las notificaciones se agregaron dos pruebas. Una comprueba que el panel muestra los ocho eventos más recientes y que los enlaces anteriores con filtros redirigen a la Bitácora; la otra, que una notificación asignada por error a otra cuenta no revela el movimiento ajeno. La suite quedó en **122 pruebas correctas de 122** y la cobertura total en **83 %: 2.258 sentencias, 382 sin ejecutar**. La migración `0011_datos_demo_realistas` reemplaza solo los textos originales de la demostración («de prueba», «Dirección ficticia…») por nombres y direcciones inventados pero verosímiles; los datos editados manualmente no se modifican. `makemigrations --check` no encontró cambios pendientes y `coverage report --fail-under=80` terminó correctamente. Las cifras de las secciones anteriores corresponden a versiones previas y se conservan como historial; las vigentes son las de esta sección. Esta comprobación usó SQLite en memoria (`config.settings.testing`) y no incluye el despliegue HTTPS con MySQL.

## Hallazgo real CF03: coordenadas de gráficos con coma decimal

Fecha de revisión: 10 de noviembre de 2026. Al incorporar los gráficos del panel de Seguimiento y del informe de movimientos, la revisión en el navegador con capturas automatizadas registró errores de consola como `<rect> attribute x: Expected length, "688,5"`. La configuración regional `es-cl` hace que Django escriba los decimales con coma y SVG solo admite punto, por lo que las barras no se dibujaban. La corrección en `beneficios/charts.py` entrega las coordenadas como texto con punto decimal. La prueba `test_report_chart_totals_match_the_filtered_movements` verifica que ningún atributo numérico del SVG contenga coma; se comprobó que falla con la versión anterior y pasa con la corrección.

## Parámetros, usuarios, gráficos y avisos

Se agregaron `test_system_parameters.py` (5 pruebas: valores por defecto, guardado con registro de cada cambio en la bitácora, rechazo de valores fuera de rango, acceso denegado al beneficiario y efecto real de cada parámetro en el bloqueo de ingreso, la sesión, el pago y el registro), `test_charts.py` (3 pruebas) y dos pruebas en `test_user_management.py` (saldo y tarjeta en la tabla, orden por fecha de alta y bloqueo de tarjeta desde administración con su registro). La suite quedó en **132 pruebas correctas de 132** y la cobertura total en **85 %: 2.435 sentencias, 355 sin ejecutar**. La migración `0012_parametros_sistema` crea la tabla de parámetros; `scripts/mysql_local.py` otorga a la cuenta de aplicación solo lectura, inserción y actualización de sus columnas. Mientras administración no guarde valores, rigen los de `config/settings/base.py`.

## Hallazgo real CF04: entradas con caracteres que la pauta OWASP pide rechazar

Fecha de revisión: 10 de noviembre de 2026. Al contrastar el prototipo con la pauta OWASP del curso («validar ingreso de caracteres peligrosos: < > " ' % ( ) & + \ … Todas las fallas en la validación deben terminar en el rechazo del dato de entrada») se comprobó formulario por formulario que el nombre de un comercio aceptaba `<script>` y que la descripción de un reporte aceptaba `<b> & "`. No era una vulnerabilidad explotable porque Django escapa la salida, pero no cumplía la pauta. También se detectó que las categorías de comercio y las preguntas de Ayuda estaban escritas en el código, contra los puntos «listas de despliegue en tablas» y «resultados que provengan de datos almacenados».

La corrección agrega `reject_dangerous_characters` en `beneficios/validators.py` y lo aplica a todos los campos de texto libre: reportes y respuestas, notas de restablecimiento, datos y búsqueda de comercios, búsqueda de usuarios, filtro de informes y código QR. Los nombres del perfil ya no admiten apóstrofo y el nombre de usuario ya no admite `+`. La migración `0013_categorias_y_ayuda` crea las tablas `MerchantCategory` y `HelpTopic` con los valores anteriores, y la dirección de ejemplo «O'Higgins» pasa a «Av. Alameda». Se ajustaron dos pruebas que aceptaban esos caracteres a propósito y se agregó `test_owasp_inputs.py` (5 pruebas). La suite quedó en **137 pruebas correctas de 137** y la cobertura total en **87 %: 2.464 sentencias, 328 sin ejecutar**.

## Hallazgo real CF05: migración incompatible con MySQL

Fecha de revisión: 11 de noviembre de 2026. Al ejecutar la preparación del modo de presentación (`scripts/arranque_seguro.py --solo-preparar`) sobre la instancia MySQL 8.4.13, la migración `0012_parametros_sistema` falló con el error 3818: «Check constraint 'system_parameters_single_row' cannot refer to an auto-increment column». La suite no lo había detectado porque usa SQLite, que sí admite esa restricción. Con el error, `iniciar.cmd` se habría detenido antes de levantar el sitio.

La corrección define en `SystemParameters` una clave primaria explícita sin autoincremento (`PositiveSmallIntegerField`, valor 1), compatible con la restricción de fila única. La migración `0012` aún no estaba aplicada en MySQL, por lo que se corrigió en su lugar; la base de desarrollo se revirtió a `0011` y se volvió a migrar. Antes de migrar se respaldó la carpeta de datos de MySQL en `.runtime/respaldos/`.

Comprobación posterior sobre MySQL: la preparación aplicó `0012` y `0013` y otorgó los permisos por tabla; `scripts/mysql_local.py verificar` confirmó TLS 1.3, lecturas y escrituras denegadas a la cuenta de consulta y rechazo de conexiones sin TLS; `scripts/verificar_https.py` pasó completo; el recorrido de todas las pantallas en HTTPS con MySQL no registró errores ni enlaces rotos (72 revisados), y la cuenta de aplicación pudo insertar y actualizar la fila de parámetros dentro de una transacción revertida. La revisión de código completa está en `docs/REVISION_CODIGO.md`.

## Registro de páginas en la terminal (R-07)

Fecha: 11 de noviembre de 2026. Se agregó `RequestLogMiddleware`, que escribe en la terminal una línea por página atendida con hora, método, ruta, estado, tiempo y perfil (`beneficiario #id`, `administrador #id` o `visitante`). `test_request_log.py` (3 pruebas) comprueba que la línea no incluye parámetros de consulta ni el nombre de usuario, que las redirecciones de visitantes quedan registradas y que los archivos estáticos y las comprobaciones periódicas de sesión no generan líneas. La suite quedó en **140 pruebas correctas de 140** y la cobertura total en **87 %: 2.482 sentencias, 328 sin ejecutar**.

## Identidad visual (datos del servidor)

Fecha: 11 de noviembre de 2026. `test_identidad_visual.py` (9 pruebas) comprueba los datos que alimentan el nuevo diseño: la categoría del comercio de cada compra (desde el pago o, en los datos de demostración anteriores, desde la descripción «Compra en …»), los totales de abonos y compras por día respetando los filtros, la línea de tendencia con punto decimal, la variación de cada indicador del panel respecto de las 24 horas anteriores y si ese cambio es favorable, el saludo según la hora y la sección de cada página. La suite quedó en **149 pruebas correctas de 149** y la cobertura total en **87 %: 2.562 sentencias, 328 sin ejecutar**.
