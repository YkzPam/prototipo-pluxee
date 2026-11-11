# Registro de revisión de código

La guía de construcción del prototipo pide revisar el código regularmente (*code review*). Este registro documenta la revisión técnica de la última iteración, sus hallazgos y cómo se resolvió cada uno. Cada corrección quedó cubierta por una prueba automatizada que falla con el código anterior y pasa con el corregido.

## Alcance y método

- **Fecha:** 10 y 11 de noviembre de 2026.
- **Versión revisada:** rama `fix/clave-temporal-admin`, paquete generado por `scripts/entregar.py`.
- **Modalidad:** revisión técnica con ejecución real del prototipo. La validación final corresponde a un integrante del equipo (sección «Aprobación»).
- **Qué se revisó:**
  1. Contraste del código con la *Guía para la construcción del Prototipo Funcional* y con la *Pauta de evaluación de interfaz y seguridad OWASP* del curso, punto por punto.
  2. Lectura de las vistas, formularios, modelos, migraciones y plantillas modificadas.
  3. Ejecución de la suite (`manage.py test`) con cobertura.
  4. Recorrido automatizado de las 37 pantallas en escritorio y móvil, como beneficiario, administrador y visitante, revisando errores de JavaScript, consola, desbordamiento, imágenes rotas, IDs duplicados y enlaces internos.
  5. Flujos completos en el navegador: reporte y respuesta, alta y baja de comercios, pago con clave dinámica y comprobante PDF, tarjeta bloqueada, cierre de otras sesiones, tema oscuro y descargas CSV.
  6. Ejecución en el modo de presentación (HTTPS con MySQL) con `scripts/arranque_seguro.py`, `scripts/mysql_local.py verificar` y `scripts/verificar_https.py`.

## Lista de verificación aplicada

| Área | Criterio | Resultado |
|---|---|---|
| Control de acceso (A01) | Cada vista administrativa exige el perfil; las consultas filtran por la cuenta autenticada | Cumple |
| Criptografía (A02) | Contraseñas con hash, campos sensibles cifrados, TLS en web y MySQL | Cumple |
| Inyección (A03) | ORM parametrizado; entradas validadas por tipo, rango, largo y caracteres | Corregido en CF04 |
| Autenticación | Bloqueo por intentos, clave temporal con cambio obligatorio, campos de contraseña ocultos | Corregido en CF02 |
| Sesiones | Identificadores del framework, cierre completo, inactividad configurable | Cumple |
| Datos y salidas | Listas y resultados desde tablas, no desde el código | Corregido en CF04 |
| Portabilidad | Las migraciones funcionan en SQLite (pruebas) y en MySQL (presentación) | Corregido en CF05 |
| Interfaz | Coherencia visual, contraste WCAG en ambos temas, vista móvil | Corregido en R-01, R-05 y R-06 |
| Registro | Actividad visible en la terminal sin datos personales | Corregido en R-07 |
| Pruebas | Cobertura sobre 80 % y una prueba por corrección | Cumple: 149 pruebas, 87 % |

## Hallazgos y resolución

| N.º | Severidad | Hallazgo | Archivo | Resolución | Prueba |
|---|---|---|---|---|---|
| CF02 | Alta | La contraseña restablecida por el administrador no obligaba a cambiarla, contra la pauta («obligar el cambio de contraseñas temporales») | `beneficios/views_users.py` | La clave asignada queda marcada como temporal y el usuario debe cambiarla al ingresar | `test_admin_reset_assigns_temporary_password_that_must_be_changed` |
| CF03 | Media | Los gráficos no se dibujaban: la configuración `es-cl` escribía coordenadas SVG con coma decimal | `beneficios/charts.py` | Coordenadas emitidas como texto con punto decimal | `test_report_chart_totals_match_the_filtered_movements` |
| CF04 | Media | Formularios que aceptaban `< > " ' % ( ) & + \`; categorías y preguntas de Ayuda escritas en el código | `beneficios/validators.py`, formularios, migración `0013` | Validador común en todos los campos de texto libre; tablas `MerchantCategory` y `HelpTopic` | `test_owasp_inputs.py` |
| CF05 | Alta | La migración de parámetros fallaba en MySQL: restricción `CHECK` sobre una columna autoincremental. SQLite la aceptaba, por eso las pruebas no la detectaron | `beneficios/models.py`, migración `0012` | Clave primaria explícita sin autoincremento | Ejecución de `arranque_seguro.py` y `verificar_https.py` sobre MySQL |
| R-01 | Baja | Cinco elementos con contraste insuficiente en tema oscuro (orden activo, tarjetas de servicios, etiquetas, avatares, «Sin leer») | `static/css/fluidez.css` | Colores específicos para el tema oscuro; contraste medido entre 8,4:1 y 12,9:1 | Medición automatizada de contraste |
| R-02 | Baja | Una transición entre páginas omitida dejaba un error rojo en la consola | `static/js/preferences-init.js` | Promesas de la transición manejadas y transición omitida cuando el movimiento está pausado | Recorrido sin errores de consola |
| R-04 | Media | El despliegue (`entregar.py --desplegar`) fallaba siempre: la comprobación de salud buscaba el título anterior «Prototipo Pluxee» y el sitio ya se llamaba «Portal de beneficios» | `scripts/desplegar_demo.py` | La comprobación busca el título vigente; despliegue completado y registrado en `dist/despliegue_local.json` | Despliegue real con verificación HTTPS y MySQL del candidato |
| R-05 | Media | En tema oscuro, la pantalla de ingreso mostraba texto claro sobre campos blancos y el título oscuro sobre fondo oscuro | `static/css/fluidez.css` | Colores del formulario de ingreso para el tema oscuro; contraste medido entre 9,1:1 y 16,5:1 | Medición automatizada de contraste |
| R-03 | Baja | Con «sin movimiento» en Apariencia, un aviso flotante no se habría cerrado | `static/js/avisos.js` | El aviso se retira de inmediato cuando no hay animación de salida | Revisión del código |
| R-06 | Media | En tema oscuro, la variable `--purple` pasa a lavanda claro, pero varios bloques conservaban un fondo claro fijo: respuesta del administrador en reportes, panel de clave dinámica, confirmaciones de desactivación (usuarios y comercios), aviso de ayuda, filtros de movimientos, tarjeta verde, marcadores de pasos y saldo del resumen de pago. Texto claro sobre fondo claro (1:1 a 1,8:1) | `static/css/fluidez.css` (secciones 12 y 13) | Superficies oscuras para esos bloques, texto morado oscuro sobre el verde de marca y grises secundarios ajustados también en tema claro | Auditoría automatizada de contraste en 101 páginas por tema: ningún texto real bajo 4,5:1 (3:1 en texto grande). Los avisos restantes corresponden a texto blanco sobre degradados morados (barra lateral, ingreso, registro), revisados en captura |
| R-07 | Baja | El servidor HTTPS no mostraba en la terminal las páginas atendidas, y cada conexión rechazada por un navegador sin el certificado instalado imprimía un error | `beneficios/middleware.py`, `servidor_seguro.py` | Una línea por página (hora, método, ruta, estado, tiempo y perfil, sin parámetros ni nombres) y un único aviso por minuto con la instrucción para instalar el certificado | `test_request_log.py` |
| R-08 | Baja | Al contrastar el README con la *Guía para la construcción del Prototipo Funcional* faltaba explicar los tres servicios (entrada, proceso y resultado), la equivalencia con la estructura de código sugerida, la aplicación de SOLID y Clean Code, los compromisos técnicos y el uso de listas cerradas; además indicaba un repositorio privado que ya es público | `README.md` (secciones 4.1 a 4.4 y 5) | Secciones agregadas con referencias a los archivos reales; cada afirmación se comprobó en el código | Revisión documental |
| R-09 | Media | Las ejecuciones del CI de los commits `22a2dc0`, `47ecb2a` y `3446b36` fallaron al instalar bibliotecas del sistema con `apt-get`, antes de correr las pruebas. Reintentar no bastó: el repositorio de paquetes de Ubuntu del ejecutor siguió fallando | `.github/workflows/verificacion.yml` | El CI ya no depende de `apt-get`: instala las dependencias sin `mysqlclient`, que solo usa el modo de presentación con MySQL; las pruebas usan SQLite | Suite completa en un entorno limpio sin `mysqlclient`: 140 pruebas correctas y 86 % de cobertura |

## Decisiones registradas

- **Apóstrofo en nombres:** la pauta lista `'` entre los caracteres a rechazar. Se aplicó al pie de la letra; un nombre como «O'Ryan» ahora se rechaza. Si el equipo prefiere admitirlo en nombres, basta con añadirlo a los caracteres permitidos de `ProfileForm._name`.
- **Eliminación de cuentas y comercios:** se desactivan en lugar de borrarse, para conservar la bitácora y el historial (Ley N.º 21.459 y trazabilidad de auditoría).
- **Bloqueo por intentos:** temporal (15 minutos) y con umbral configurable en Parámetros, en vez de una deshabilitación permanente que requeriría intervención manual.

## Aprobación del equipo

Un integrante distinto del autor debe revisar los cambios y registrar su conformidad. Pasos sugeridos: leer este registro, ejecutar `verificar.cmd`, iniciar `iniciar.cmd` y recorrer las secciones de la guía de presentación.

| Revisor | Fecha | Versión o paquete revisado | Resultado | Observaciones |
|---|---|---|---|---|
| | | | | |
