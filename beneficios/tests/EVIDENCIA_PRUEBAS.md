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
