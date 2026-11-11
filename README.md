# Prototipo académico Pluxee Chile

Aplicación web funcional de la evaluación 3 de Ingeniería de Software. La evaluación 4 corresponde al informe de diagramas y pruebas. Este proyecto continúa el caso académico de consultas interrumpidas y cierres de sesión; no modifica ni se conecta a los sistemas reales de Pluxee.

## 1. Inicio en este equipo

1. Ejecutar `iniciar.cmd` dentro de esta carpeta.
2. Abrir **https://127.0.0.1:8443** en el navegador después de configurar la confianza del certificado local.
3. Mantener abierta la ventana del servidor durante la demostración. `Ctrl+C` lo detiene.

El inicio está preparado para Windows con Python 3.12 o superior. `preparar.cmd` instala las dependencias de Python. En el primer inicio se descarga y comprueba el archivo oficial de MySQL Community 8.4.13. La instancia queda en este equipo, sin instalar un servicio de Windows y sin aceptar tráfico de la red. Los archivos de la base de datos y las claves se generan localmente y quedan fuera del ZIP.

El certificado público se genera en `.runtime/security/web_tls/Pluxee_Prototipo_Local.crt`, válido para `127.0.0.1` y `localhost`. El inicio no modifica la confianza de Windows ni del navegador. Para verificar la conexión sin cambiar esa configuración, se puede usar `curl.exe --cacert .runtime/security/web_tls/Pluxee_Prototipo_Local.crt https://127.0.0.1:8443/ingresar/` con un cliente compatible, o el cliente de Python indicado en la verificación. Para detener también MySQL al terminar, ejecutar `python scripts/mysql_local.py detener` con el Python del entorno virtual.

| Usuario de prueba | Contraseña inicial | Función |
|---|---|---|
| `beneficiario` | `Prototipo2026!` | Cuenta de Camila para consultar saldo y movimientos, buscar comercios y realizar pagos académicos. |
| `beneficiario2` | `Prototipo2026!` | Cuenta de Diego para comprobar la separación entre cuentas. |
| `sinmovimientos` | `Prototipo2026!` | Cuenta sin operaciones que muestra un resultado vacío válido. |
| `administrador` | `AdminPluxee2026!` | Bitácora y escenarios controlados de disponibilidad. |

Las cuentas de demostración permiten ingresar directamente con su usuario y contraseña. Si se personalizó la contraseña, se utiliza la vigente. El PIN de pago ficticio es **`4826`**. La tabla contiene credenciales públicas del ejercicio. El cambio voluntario está disponible en **Mi perfil** para beneficiarios y en el menú de administración para el administrador.

## 2. Funciones disponibles

La navegación principal utiliza Inicio, Pagar, Comercios y Mi perfil. El saldo y los movimientos provienen de MySQL. Los filtros se comprueban en el servidor y las operaciones del beneficiario se limitan a su propia cuenta.

- **Acceso y sesión:** ingreso, bloqueo temporal por intentos fallidos y aviso antes del vencimiento. Si la sesión termina durante una consulta, al autenticarse nuevamente se vuelve a la vista de consulta, con sus filtros de movimientos cuando corresponda.
- **Crear usuario:** en la pantalla de ingreso, el enlace abre el registro de un beneficiario con tarjeta, PIN y un abono inicial de demostración de $48.000, registrado en sus movimientos.
- **Saldo y movimientos:** consulta actualizada, filtros, historial vacío, interrupción diferenciada y reintento. El inicio indica qué consultas están interrumpidas y permite reintentarlas. La tarjeta de saldo reúne el importe, su estado, la hora de confirmación y la acción disponible. Durante una interrupción muestra «Saldo sin actualizar» si la sesión tiene un valor previo o «Saldo no disponible» si aún no lo tiene.
- **Comercios:** catálogo ficticio, búsqueda por nombre o código, categoría, comuna y favoritos por usuario.
- **Pago académico:** Pago Online, Pago QR con selección o ingreso del código del comercio ficticio, Clave Dinámica de cuatro dígitos y tarjeta de prueba. La clave se genera con el PIN del ejercicio, tiene una vigencia de hasta 90 minutos y se consume con un único cargo confirmado en la sesión que la generó. El comprobante privado muestra el medio utilizado. Repetir una confirmación conserva un único cargo.
- **Mi tarjeta y perfil:** bloqueo o activación de la tarjeta ficticia, edición del nombre de prueba y acceso al cambio de contraseña.
- **Actividad de mi cuenta y reportes:** desde Mi perfil se pueden revisar los ingresos y cierres de sesión de la propia cuenta. Ayuda y el aviso de interrupción enlazan al formulario de reportes. La cuenta recibe un folio y puede consultar su estado y la respuesta del administrador.
- **Seguimiento y Bitácora:** el panel de Seguimiento reúne los indicadores de las últimas 24 horas (ingresos rechazados, accesos sin permiso, sesiones vencidas), el estado de los servicios, las interrupciones recientes y los últimos eventos. La sección Bitácora concentra todos los eventos con filtros, el detalle de cada interrupción con sus consultas pendientes y la descarga de los registros filtrados como CSV con fecha y hora, tipo de evento, resultado y duración registrada.
- **Bandeja y comprobaciones:** el administrador filtra los reportes por problema y estado, los pasa de Recibido a En revisión y luego a Resuelto. Cuando comprueba la recuperación de una interrupción ya restablecida, puede dejar una nota fechada en su ficha.
- **Administrar usuarios:** en «Usuarios» se pueden crear beneficiarios, buscarlos por nombre de usuario, filtrarlos por estado y ordenarlos por usuario, fecha de alta o último ingreso. La tabla muestra estado, tarjeta, saldo y último ingreso. La ficha resume la cuenta y permite editar nombre y apellido, asignar una contraseña temporal que el usuario debe cambiar al ingresar, bloquear o activar la tarjeta y desactivar o reactivar el acceso. La desactivación conserva el historial e invalida las sesiones anteriores.
- **Parámetros del sistema:** el administrador ajusta, dentro de rangos validados en el servidor, el abono inicial de registro, los intentos de ingreso antes del bloqueo, los minutos de inactividad de la sesión y el monto máximo por compra. Los cambios se aplican sin reiniciar el servidor y la bitácora registra el valor anterior y el nuevo.
- **Gráficos y avisos:** el panel muestra los eventos por hora de las últimas 24 horas y el informe muestra abonos y compras por día o por semana. Los mensajes de éxito aparecen como avisos flotantes que se cierran solos; los errores permanecen en la página.
- **Abonos y cargos:** el administrador puede registrar un abono ficticio y ver los últimos movimientos de cada cuenta. Los abonos y los cargos de pagos confirmados quedan en MySQL y aparecen en la terminal del servidor con su ID y tipo de movimiento.
- **Resumen semanal y tarjeta:** Inicio muestra los gastos por bloques de días del mes con enlaces a las compras correspondientes. Mi perfil muestra la tarjeta y su estado, además del acceso a las sesiones vigentes.
- **Notificaciones:** la campana abre los avisos de movimientos nuevos y respuestas de administración. Cada cuenta puede marcar sus propios avisos como leídos.
- **Revisión del pago:** el formulario permite revisar el comercio, importe y saldo resultante antes de confirmar el cargo. La autorización vence y el servidor vuelve a comprobar el saldo al confirmar.
- **Movimiento visual:** el pie permite pausar las animaciones. La página respeta la preferencia de movimiento reducido del sistema.
- **Apariencia:** el acceso superior abre los temas claro, oscuro y del sistema, contraste, intensidad de movimiento y avatar. Estas preferencias se guardan en el navegador; el avatar y la privacidad de importes se distinguen por cuenta.
- **Navegación:** Buscar o Ctrl + K abre las acciones disponibles. El recorrido inicial es opcional y puede abrirse nuevamente desde Apariencia. Los movimientos se agrupan por día y abren un panel de detalle.
- **Gestión administrativa:** Comercios permite altas, edición y cambios de estado conservando el historial. Las incidencias admiten prioridad, responsable e historial de actualizaciones. Informes permite consultar movimientos por fechas y descargar el CSV con los mismos filtros.

## 3. Recorrido para la presentación

1. Ingresar como `beneficiario`, consultar el saldo y revisar los movimientos.
2. Buscar un comercio, marcarlo como favorito y abrir «Pagar aquí».
3. Confirmar un monto de prueba con el PIN `4826`, revisar el comprobante y comprobar el nuevo movimiento.
4. Bloquear la tarjeta de prueba y comprobar que un nuevo pago sea rechazado sin generar un cargo. Activarla nuevamente.
5. Mantener la sesión del beneficiario en una ventana y abrir administración en un perfil de navegador independiente. Consultar el saldo como beneficiario, inducir una interrupción como administrador y reintentar como beneficiario en la misma sesión. Revisar el aviso «Saldo sin actualizar» y la fecha del último valor confirmado. Restablecer el servicio, repetir la consulta y revisar el intervalo registrado en el panel administrativo.
6. Mostrar el rechazo del panel administrativo al usar un beneficiario. La prueba automatizada también verifica intentos de consultar otra cuenta y de reutilizar una sesión cerrada.

Para demostrar la espera entre reintentos, consultar el saldo durante la interrupción y observar la cuenta regresiva informada por el servidor. Después de restablecer el servicio y terminar la espera, el botón permite solicitar un saldo actualizado. Las pruebas automatizadas también comprueban que una solicitud directa anticipada recibe HTTP 429. El fallo original y su comprobación están registrados en `beneficios/tests/EVIDENCIA_PRUEBAS.md`.

## 4. Organización técnica

El modelo es incremental: acceso y sesión, consultas, seguimiento y funciones adicionales comparten usuarios, permisos y persistencia. Django controla autenticación, sesiones, formularios, ORM y CSRF. Las vistas coordinan el recorrido; `services.py` adapta los datos académicos; `responses.py` construye respuestas diferenciadas; `events.py` notifica el registro de eventos. `policies.py` conserva únicamente configuración inmutable por proceso, sin un usuario compartido.

El saldo se calcula como abonos menos cargos. MySQL confirma el movimiento y el comprobante en una transacción que bloquea la cuenta durante el pago y utiliza una referencia única por usuario. Una falla de auditoría obligatoria revierte el cargo. La cuenta SQL de consulta solo puede leer las tablas de saldo, movimientos y disponibilidad que necesita ese recorrido. La cuenta de la aplicación escribe en las tablas y columnas que necesita para operar. El aprovisionamiento de esquemas utiliza una credencial distinta.

El informe de la evaluación 2 dejó la estructura física sujeta al gestor académico que se eligiera (p. 64). El borrador posterior consideró SQLite. En la implementación se seleccionó MySQL para demostrar permisos diferenciados en el propio motor; SQLite se conserva para desarrollo y pruebas aisladas.

## 5. Verificación y entornos

`verificar.cmd` comprueba el proyecto y ejecuta las pruebas con cobertura. `python scripts/entregar.py` ejecuta la verificación, comprueba las migraciones, recopila los recursos y genera el ZIP; detiene el proceso si falla un paso. Los archivos de `beneficios/tests/` conservan casos, salidas y la evidencia de una corrección real. La configuración de integración continua está en `.github/workflows/verificacion.yml`; comprueba y prepara un paquete en GitHub Actions con cada envío al repositorio privado `YkzPam/prototipo-pluxee`. La primera ejecución (#1, commit `d4c9a02`) terminó correctamente el 11 de noviembre de 2026. No existe un despliegue remoto: el despliegue es local (sección 5.1).

La rama `evaluacion-3` contiene la entrega de la Evaluación 3 (prototipo). Las etapas siguientes, como el informe de la Evaluación 4, se publicarán en ramas propias sin sustituir esta. La entrega se identifica con la rama y el hash del commit publicado en GitHub.

En Windows, `.venv\Scripts\python.exe scripts\entregar.py --desplegar` ejecuta el proceso completo. El ZIP verificado se extrae en una carpeta que se identifica por su huella. La versión candidata inicia en otro puerto local y se comprueba con HTTPS y MySQL antes de pasar al puerto 8443. Las versiones comparten los datos locales y las claves del equipo. El resultado queda en `dist/verificacion_local.txt` y `dist/despliegue_local.json`.

### 5.1 Pipeline de integración y despliegue continuo (CI/CD)

El proyecto tiene un pipeline local que se ejecuta con una sola orden y se detiene en el primer paso que falla. Cada etapa corresponde a una práctica de integración o despliegue continuo:

| Etapa | Orden | Qué garantiza |
|---|---|---|
| 1. Verificación estática | `manage.py check` | Configuración y modelos sin errores |
| 2. Pruebas con cobertura | `coverage run manage.py test` | Toda la suite pasa en una base descartable |
| 3. Umbral de calidad | `coverage report --fail-under=80` | La cobertura no baja de 80 % |
| 4. Migraciones | `makemigrations --check --dry-run` | Los modelos y las migraciones coinciden |
| 5. Recursos | `collectstatic --noinput` | Los recursos estáticos se pueden publicar |
| 6. Paquete | ZIP con comprobación de integridad | Solo código y documentación; sin bases, claves ni certificados |
| 7. Despliegue candidato (`--desplegar`) | Versión extraída en `.runtime/releases/<huella>` en un puerto libre | La versión nueva se prueba sin detener la que está en uso |
| 8. Verificación del candidato | `scripts/verificar_https.py` sobre MySQL | TLS, cookies, CSRF, sesiones, permisos y un pago real sin duplicados |
| 9. Activación con vuelta atrás | Reemplazo en el puerto 8443 | Si la nueva versión no responde, se reactiva la anterior |

La misma secuencia de las etapas 1 a 6 se ejecuta en GitHub Actions (`.github/workflows/verificacion.yml`) con cada envío al repositorio; el historial está en la pestaña Actions de `YkzPam/prototipo-pluxee`. La revisión de código de la última iteración está en `docs/REVISION_CODIGO.md` y la secuencia de la exposición en `docs/GUIA_PRESENTACION.md`.

| Perfil | Configuración y alcance |
|---|---|
| Desarrollo local | `config.settings.development`; SQLite separado, servidor ligado a `127.0.0.1` y HTTP local. |
| Pruebas | `config.settings.testing`; SQLite descartable en memoria, mismas reglas de negocio. |
| Demostración HTTPS | `config.settings.production`; MySQL local, conexión de consulta de solo lectura, certificado TLS y cookies Secure. |

El perfil de demostración usa HTTPS, HSTS y cookies Secure. Las cuentas de MySQL verifican el certificado del motor y solo aceptan conexiones cifradas. La comprobación automatizada del sitio usa el certificado local de forma explícita, sin desactivar su validación. La prueba de comprensión con cinco participantes y la exposición se realizan por separado.

La salida de `scripts/entregar.py` registra el número de pruebas y la cobertura de la versión empaquetada. El intento anterior de carga en SQLite quedó interrumpido: sus eventos persistidos y las condiciones de la interrupción están en `beneficios/tests/perfil_carga_parcial.json`. Ese resultado no se atribuye a la versión MySQL ni sirve para afirmar que se completaron diez minutos de prueba.

Los campos sensibles se cifran con AES-256-GCM. Las contraseñas y el PIN se someten a hash antes de cifrar ese resultado. Las claves quedan fuera del repositorio, protegidas mediante DPAPI para el usuario de Windows. La separación de permisos SQL no equivale a aislar procesos ejecutados por ese mismo usuario. Las sesiones anteriores a la migración se descartan. Los formularios conservan CSRF y la bitácora excluye contraseñas, PIN e identificadores de sesión reutilizables.

## 6. Evidencia de seguridad para la Evaluación 3

### 6.1 Controles revisados y resultados

La revisión técnica del 9 de noviembre de 2026 examinó los permisos por perfil y por cuenta, los formularios de ingreso y consulta, la expiración de sesiones y la configuración de HTTPS y MySQL. La tabla relaciona los riesgos de OWASP Top 10:2021 solicitados por la guía con pruebas del prototipo (OWASP Foundation, 2021). El control de acceso y el cifrado se vinculan con las áreas descritas por ISO/IEC 27002:2022 (International Organization for Standardization, 2022). El alcance de esa relación corresponde a los controles enumerados y a los recorridos comprobados en el entorno local.

| Riesgo o área de control | Implementación revisada | Resultado comprobado |
|---|---|---|
| OWASP A01 y control de acceso | `beneficios/security.py` exige autenticación y comprueba el perfil administrativo. `beneficios/views.py` consulta por identificador de cuenta y usuario autenticado. `beneficios/views_support.py` limita el historial del beneficiario a sus reportes. | En HTTPS, el beneficiario recibió HTTP 403 al solicitar Seguimiento y la cookie invalidada recibió HTTP 401 en la API. Las pruebas de `test_workflows.py` cubren cambios de identificador y acceso administrativo. |
| Autenticación y sesión | Django almacena el hash de la contraseña. `beneficios/security.py` limita los intentos fallidos y `beneficios/middleware.py` aplica el vencimiento de la sesión y la política de cambio de contraseña temporal. | `test_lockout_rejects_even_correct_password_until_timeout` comprueba el bloqueo temporal. En HTTPS se creó una cuenta sintética con contraseña temporal. El cambio habilitó el acceso y la sesión anterior recibió HTTP 401. `test_user_management.py` comprueba que la contraseña restablecida por el administrador obliga al cambio (hallazgo CF02). |
| OWASP A02 y criptografía | `config/settings/production.py` configura HTTPS, HSTS y cookies seguras. `config/settings/database_secure.py` verifica la identidad TLS del servidor MySQL. `config/encrypted_fields.py` cifra campos seleccionados con AES-GCM y `config/vault.py` protege las claves mediante DPAPI. | La web y las dos conexiones de aplicación a MySQL usaron TLS 1.3. La verificación HTTPS confirmó Secure, HttpOnly y SameSite=Lax en la cookie de sesión. El motor rechazó el intento de ingreso sin TLS con el error 1045. |
| OWASP A03 e inyección | Los formularios validan tipo, rango y largo de las entradas. `beneficios/validators.py` rechaza en todos los campos de texto libre los caracteres que lista la pauta (`< > " ' % ( ) & + \` y el carácter nulo). `beneficios/services.py` aplica los filtros de movimientos mediante el ORM de Django. Las categorías de comercio y las preguntas de Ayuda se leen de tablas, no del código. La cuenta SQL de consulta opera con permisos restringidos. | `test_input_validation_rejects_missing_oversized_and_injection_inputs` comprueba el rechazo de entradas de inyección. `test_owasp_inputs.py` comprueba cada carácter de la pauta en cada formulario. `test_invalid_filters_are_rejected_without_query_result` comprueba HTTP 400. En MySQL, la cuenta de consulta recibió error 1142 al intentar escribir o leer tablas restringidas. |
| Protección de operaciones y registro | El formulario de inicio aplica CSRF. El pago registra el cargo y su comprobante dentro de una transacción. La bitácora registra el resultado de la operación y excluye las credenciales. | En HTTPS, un POST sin token recibió HTTP 403 y la repetición del mismo pago conservó un solo cargo. La prueba `test_database_audit_failure_rolls_back_payment_and_receipt_together` comprueba la reversión cuando falla el registro de auditoría. |

La revisión comprobó el caso CF01. La primera ejecución histórica devolvió HTTP 503 también para el reintento inmediato. La corrección en `beneficios/views.py` guarda la sesión antes de devolver el 503 inicial, de modo que la siguiente solicitud, durante la espera, reciba HTTP 429. La prueba reproduce la interrupción y comprueba que el saldo se recupera al restablecer el servicio y reintentar después de la espera. [Registro de pruebas](beneficios/tests/EVIDENCIA_PRUEBAS.md).

La revisión detectó que el contador de ingresos fallidos podía perder incrementos simultáneos. En una instancia MySQL 8.4.13 desechable, con aislamiento READ COMMITTED y una fila previamente creada, el ensayo controlado del código anterior registró 2 de 5 intentos. La corrección en `beneficios/security.py` bloquea la fila al actualizarla y permite repetir la transacción completa hasta dos veces si MySQL la revierte por un interbloqueo. Con el cambio, se registraron los cinco intentos tanto con la fila existente como al crearla simultáneamente. Un ensayo adicional registró 12 de 12 intentos de cuentas distintas con una IP compartida. Estos ensayos usaron contadores sintéticos y se ejecutaron por separado de la suite automatizada.

El prototipo utiliza cuentas, movimientos y comercios ficticios en un equipo local. La Ley N.º 19.628 (1999, arts. 7 y 11) sirve como referencia para la reserva y el cuidado de los datos en el diseño, y la Ley N.º 21.459 (2022, arts. 2 y 4) orienta la discusión sobre acceso ilícito e integridad de los datos. Las pruebas de acceso denegado, el uso de perfiles separados y la bitácora aportan evidencia técnica dentro de ese alcance académico.

Para repetir las comprobaciones desde la carpeta del proyecto con el prototipo iniciado:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\verificar_https.py
.\.venv\Scripts\python.exe -X utf8 scripts\mysql_local.py verificar
```

### 6.2 Secuencia de exposición y comprobación del equipo

La exposición comienza con la decisión de construir un prototipo incremental. El acceso, las consultas y el seguimiento se incorporaron por etapas y operan sobre una base compartida. La demostración abre con el ingreso del beneficiario y continúa con tres servicios completos. Para mostrar la interfaz y la experiencia de uso, el recorrido incluye el mensaje de interrupción, el último saldo confirmado con su hora y la recuperación de la consulta. En una vista móvil del navegador se puede comprobar que la navegación, los avisos y los botones siguen visibles y utilizables.

| Servicio | Entrada y proceso | Resultado que se muestra |
|---|---|---|
| Consulta de saldo | Consultar el saldo, interrumpir el servicio desde un perfil de navegador separado con la cuenta administradora y reintentar. Restablecer el servicio al concluir la espera. | Saldo confirmado, aviso «Saldo sin actualizar» y recuperación del dato. El intervalo de la interrupción aparece en Seguimiento. |
| Consulta de movimientos | Seleccionar un tipo de movimiento o rango de fechas. El servidor valida los filtros y consulta los registros de la cuenta autenticada. | Lista filtrada. Con un intervalo válido sin registros, la pantalla muestra un estado vacío. |
| Pago académico | Elegir Pago QR, ingresar un código del catálogo de prueba y confirmar un monto con el PIN ficticio. El servidor comprueba el comercio y el saldo antes de registrar el cargo. | Comprobante y nuevo movimiento de la cuenta. La verificación HTTPS comprueba que repetir la confirmación conserva un único cargo. |

Para cerrar el ensayo, el grupo puede intentar abrir Seguimiento desde la sesión beneficiaria, mostrar el rechazo y contrastarlo con la bitácora de la cuenta administradora. Al cerrar la sesión, la aplicación pide autenticarse para volver a una vista protegida. La persona que revise el código puede repetir el caso CF01, consultar el cambio y dejar una nota con su nombre, fecha, versión revisada, caso ejecutado y resultado observado. La guía asigna al grupo la definición de su representante y evalúa los pasos durante la presentación.

## 7. Referencias del diseño y la implementación

La organización visual toma como referencia las funciones públicas de la aplicación Pluxee Chile y su manual Junaeb. La implementación, el catálogo y los datos del ejercicio son independientes; no se reproducen promociones vigentes ni se presentan comercios ficticios como adheridos reales.

- Pluxee Chile. (s. f.). [Pluxee App](https://www.pluxee.cl/productos/descarga-pluxee-app/).
- Pluxee Chile. (2026). [Manual guía usuario Junaeb](https://lp.pluxee.cl/hubfs/JUNAEB%202026/ARCHIVOS/2026_MANUAL%20GU%C3%8DA%20USUARIO.pdf).
- Django Software Foundation. (s. f.). [Security in Django](https://docs.djangoproject.com/en/5.2/topics/security/).
- Django Software Foundation. (s. f.). [How to use sessions](https://docs.djangoproject.com/en/5.2/topics/http/sessions/).
- Django Software Foundation. (s. f.). [MySQL notes](https://docs.djangoproject.com/en/5.2/ref/databases/#mysql-notes).
- International Organization for Standardization. (2022). [Information security, cybersecurity and privacy protection — Information security controls (ISO/IEC 27002:2022)](https://www.iso.org/standard/75652.html).
- Ley N.º 19.628, Sobre protección de la vida privada. (1999). [Biblioteca del Congreso Nacional de Chile](https://www.bcn.cl/leychile/navegar?idNorma=141599).
- Ley N.º 21.459, Establece normas sobre delitos informáticos. (2022). [Biblioteca del Congreso Nacional de Chile](https://www.bcn.cl/leychile/navegar?idNorma=1177743).
- Microsoft. (s. f.). [CryptProtectData function](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata).
- Oracle. (s. f.). [Installing MySQL on Microsoft Windows using a noinstall ZIP archive](https://dev.mysql.com/doc/refman/8.4/en/windows-install-archive.html).
- OWASP Foundation. (2021). [OWASP Top 10:2021](https://top10.owasp.org/2021/).
- Python Cryptographic Authority. (s. f.). [Authenticated encryption: AESGCM](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM).

La fuente Raleway se distribuye localmente bajo SIL Open Font License; su licencia está en `static/fonts/OFL-Raleway.txt`.
