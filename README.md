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
- **Saldo y movimientos:** consulta actualizada, filtros, historial vacío, interrupción diferenciada y reintento. La tarjeta de saldo reúne el importe, su estado, la hora de confirmación y la acción disponible. Durante una interrupción muestra «Saldo sin actualizar» si la sesión tiene un valor previo o «Saldo no disponible» si aún no lo tiene.
- **Comercios:** catálogo ficticio, búsqueda por nombre o código, categoría, comuna y favoritos por usuario.
- **Pago académico:** selección del comercio, validación de monto y PIN, tarjeta activa, saldo suficiente, cargo persistido y comprobante privado. Repetir la misma confirmación conserva un único cargo.
- **Mi tarjeta y perfil:** bloqueo o activación de la tarjeta ficticia, edición del nombre de prueba y acceso al cambio de contraseña.
- **Seguimiento:** eventos y filtros para el administrador. El historial de interrupciones de prueba presenta su inicio, restablecimiento, duración y consultas pendientes registradas por el prototipo.

## 3. Recorrido para la presentación

1. Ingresar como `beneficiario`, consultar el saldo y revisar los movimientos.
2. Buscar un comercio, marcarlo como favorito y abrir «Pagar aquí».
3. Confirmar un monto de prueba con el PIN `4826`, revisar el comprobante y comprobar el nuevo movimiento.
4. Bloquear la tarjeta de prueba y comprobar que un nuevo pago sea rechazado sin generar un cargo. Activarla nuevamente.
5. Mantener la sesión del beneficiario en una ventana y abrir administración en un perfil de navegador independiente. Consultar el saldo como beneficiario, inducir una interrupción como administrador y reintentar como beneficiario en la misma sesión. Revisar el aviso «Saldo sin actualizar» y la fecha del último valor confirmado. Restablecer el servicio, repetir la consulta y revisar el intervalo registrado en el panel administrativo.
6. Mostrar el rechazo del panel administrativo al usar un beneficiario. La prueba automatizada también verifica intentos de consultar otra cuenta y de reutilizar una sesión cerrada.

Para evidenciar la corrección de reintentos, consultar el saldo durante la interrupción, pulsar de nuevo inmediatamente y comprobar que la respuesta aplica la espera. Después de restablecer el servicio y esperar ese intervalo, el siguiente intento muestra el saldo actualizado. El fallo original y su nueva comprobación están registrados en `beneficios/tests/EVIDENCIA_PRUEBAS.md`. La página se puede presentar también con una ventana angosta y navegar con Tab hasta la acción de saldo.

## 4. Organización técnica

El modelo es incremental: acceso y sesión, consultas, seguimiento y funciones adicionales comparten usuarios, permisos y persistencia. Django controla autenticación, sesiones, formularios, ORM y CSRF. Las vistas coordinan el recorrido; `services.py` adapta los datos académicos; `responses.py` construye respuestas diferenciadas; `events.py` notifica el registro de eventos. `policies.py` conserva únicamente configuración inmutable por proceso, sin un usuario compartido.

El saldo se calcula como abonos menos cargos. MySQL confirma el movimiento y el comprobante en una transacción que bloquea la cuenta durante el pago y utiliza una referencia única por usuario. Una falla de auditoría obligatoria revierte el cargo. La cuenta SQL de consulta solo puede leer las tablas de saldo, movimientos y disponibilidad que necesita ese recorrido. La cuenta de la aplicación escribe en las tablas y columnas que necesita para operar. El aprovisionamiento de esquemas utiliza una credencial distinta.

El informe de la evaluación 2 dejó la estructura física sujeta al gestor académico que se eligiera (p. 64). El borrador posterior consideró SQLite. En la implementación se seleccionó MySQL para demostrar permisos diferenciados en el propio motor; SQLite se conserva para desarrollo y pruebas aisladas.

## 5. Verificación y entornos

`verificar.cmd` comprueba el proyecto y ejecuta las pruebas con cobertura. `python scripts/entregar.py` ejecuta la verificación, comprueba las migraciones, recopila los recursos y genera el ZIP; detiene el proceso si falla un paso. Los archivos de `beneficios/tests/` conservan casos, salidas y la evidencia de una corrección real. La configuración de integración continua está en `.github/workflows/verificacion.yml`; comprueba y prepara un paquete, pero su presencia no implica que GitHub Actions se haya ejecutado o que exista un despliegue remoto.

En Windows, `.venv\Scripts\python.exe scripts\entregar.py --desplegar` ejecuta el proceso completo. El ZIP verificado se extrae en una carpeta que se identifica por su huella. La versión candidata inicia en otro puerto local y se comprueba con HTTPS y MySQL antes de pasar al puerto 8443. Las versiones comparten los datos locales y las claves del equipo. El resultado queda en `dist/verificacion_local.txt` y `dist/despliegue_local.json`.

| Perfil | Configuración y alcance |
|---|---|
| Desarrollo local | `config.settings.development`; SQLite separado, servidor ligado a `127.0.0.1` y HTTP local. |
| Pruebas | `config.settings.testing`; SQLite descartable en memoria, mismas reglas de negocio. |
| Demostración HTTPS | `config.settings.production`; MySQL local, conexión de consulta de solo lectura, certificado TLS y cookies Secure. |

El perfil de demostración usa HTTPS, HSTS y cookies Secure. Las cuentas de MySQL verifican el certificado del motor y solo aceptan conexiones cifradas. La comprobación automatizada del sitio usa el certificado local de forma explícita, sin desactivar su validación. La prueba de comprensión con cinco participantes y la exposición se realizan por separado.

La salida de `scripts/entregar.py` registra el número de pruebas y la cobertura de la versión empaquetada. El intento anterior de carga en SQLite quedó interrumpido: sus eventos persistidos y las condiciones de la interrupción están en `beneficios/tests/perfil_carga_parcial.json`. Ese resultado no se atribuye a la versión MySQL ni sirve para afirmar que se completaron diez minutos de prueba.

Los campos sensibles se cifran con AES-256-GCM. Las contraseñas y el PIN se someten a hash antes de cifrar ese resultado. Las claves quedan fuera del repositorio, protegidas mediante DPAPI para el usuario de Windows. La separación de permisos SQL no equivale a aislar procesos ejecutados por ese mismo usuario. Las sesiones anteriores a la migración se descartan. Los formularios conservan CSRF y la bitácora excluye contraseñas, PIN e identificadores de sesión reutilizables.

## 6. Referencias del diseño y la implementación

La organización visual toma como referencia las funciones públicas de la aplicación Pluxee Chile y su manual Junaeb. La implementación, el catálogo y los datos del ejercicio son independientes; no se reproducen promociones vigentes ni se presentan comercios ficticios como adheridos reales.

- Pluxee Chile. (s. f.). [Pluxee App](https://www.pluxee.cl/productos/descarga-pluxee-app/).
- Pluxee Chile. (2026). [Manual guía usuario Junaeb](https://lp.pluxee.cl/hubfs/JUNAEB%202026/ARCHIVOS/2026_MANUAL%20GU%C3%8DA%20USUARIO.pdf).
- Django Software Foundation. (s. f.). [Security in Django](https://docs.djangoproject.com/en/5.2/topics/security/).
- Django Software Foundation. (s. f.). [How to use sessions](https://docs.djangoproject.com/en/5.2/topics/http/sessions/).
- Django Software Foundation. (s. f.). [MySQL notes](https://docs.djangoproject.com/en/5.2/ref/databases/#mysql-notes).
- Microsoft. (s. f.). [CryptProtectData function](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata).
- Oracle. (s. f.). [Installing MySQL on Microsoft Windows using a noinstall ZIP archive](https://dev.mysql.com/doc/refman/8.4/en/windows-install-archive.html).
- Python Cryptographic Authority. (s. f.). [Authenticated encryption: AESGCM](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM).

La fuente Raleway se distribuye localmente bajo SIL Open Font License; su licencia está en `static/fonts/OFL-Raleway.txt`.
