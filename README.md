# Prototipo académico Pluxee Chile

Este es el prototipo web que construimos para la **Evaluación 3 de Ingeniería de Software**. Simula el portal de beneficios de alimentación Junaeb: un beneficiario puede consultar su saldo y sus movimientos, buscar comercios y pagar, y un administrador puede hacer seguimiento de todo lo que pasa en el sistema.

Partimos del caso que trabajamos en la unidad anterior: qué debería pasar cuando una consulta de saldo se interrumpe o la sesión se cierra a mitad de camino. Todo funciona con datos inventados y en tu propio computador; **no se conecta a los sistemas reales de Pluxee**.

> El informe con los diagramas y el reporte de pruebas corresponde a la Evaluación 4 y va por separado.

---

## 1. Cómo instalarlo en tu computador

Lo armamos para que funcione con un doble clic. La primera vez tarda unos minutos porque se prepara solo; después arranca en segundos.

### Lo que necesitas

- **Windows 10 u 11** (64 bits).
- **Python 3.12 o superior**. Si no lo tienes, descárgalo de [python.org](https://www.python.org/downloads/) y, en el instalador, **marca la casilla «Add python.exe to PATH»**. Es el error más común, así que vale la pena revisarlo.
- **Internet, solo la primera vez**: se descargan las librerías de Python y MySQL (unos 281 MB).
- Unos **2,5 GB libres** en el disco.
- **Chrome o Edge**.

### Paso 1. Descarga el proyecto

1. Entra a **https://github.com/YkzPam/prototipo-pluxee** y fíjate en que esté seleccionada la rama **`evaluacion-3`**.
2. Haz clic en el botón verde **Code** y luego en **Download ZIP**.

Si usas Git, también puedes clonarlo: `git clone --branch evaluacion-3 https://github.com/YkzPam/prototipo-pluxee.git`

### Paso 2. Extrae el ZIP

Clic derecho sobre el archivo → **Extraer todo…**. Te recomendamos una carpeta con una ruta corta, como `C:\Pluxee`. Importante: no lo ejecutes desde dentro del ZIP sin extraerlo, porque no va a funcionar.

### Paso 3. Inícialo

Abre la carpeta y haz doble clic en **`iniciar.cmd`**. Como el archivo viene de internet, puede que Windows te pida confirmación: elige **Ejecutar** (o **Más información → Ejecutar de todas formas**).

La primera vez vas a ver bastante texto en la ventana. Es normal: el programa está haciendo esto por su cuenta, sin que tengas que tocar nada:

1. **Instala lo que necesita Python** en una carpeta `.venv` dentro del proyecto (no toca el resto de tu computador). De esto se encarga `preparar.cmd`, que `iniciar.cmd` ejecuta por ti.
2. **Descarga MySQL 8.4.13**, revisa que el archivo sea el original (comprueba su huella SHA-256) y lo deja funcionando solo para este prototipo. No instala nada en Windows ni acepta conexiones desde otros equipos.
3. **Crea las claves, el certificado de seguridad, la base de datos y las cuentas de prueba** en la carpeta `.runtime`. Esa carpeta es solo tuya: nunca se sube a GitHub.

Sabrás que está listo cuando aparezca esta línea:

```
Prototipo académico Pluxee Chile: https://127.0.0.1:8443/
```

Desde ese momento, la ventana va mostrando cada página que visitas, como un registro en vivo. **No la cierres mientras uses el prototipo.**

### Paso 4. Haz que el navegador confíe en el certificado (solo una vez)

El prototipo usa HTTPS, igual que un sitio real. Como el certificado lo creó tu propio computador, el navegador no lo conoce y va a mostrar «La conexión no es privada». Para que confíe en él:

1. Abre la carpeta `.runtime\security\web_tls\` y haz doble clic en `Pluxee_Prototipo_Local.crt`.
2. Elige **Instalar certificado… → Usuario actual → Siguiente**.
3. Marca **Colocar todos los certificados en el siguiente almacén → Examinar… → Entidades de certificación raíz de confianza → Aceptar → Siguiente → Finalizar**. Windows te mostrará una advertencia: acéptala.
4. **Cierra el navegador por completo** y vuelve a abrirlo.

Tranquilo: este certificado solo sirve para `127.0.0.1` y `localhost`, es decir, para tu propio computador. Si después quieres quitarlo: abre `certmgr.msc` → Entidades de certificación raíz de confianza → Certificados → «Prototipo Pluxee local» → Eliminar.

### Paso 5. ¡A usarlo!

Abre **https://127.0.0.1:8443** y entra con cualquiera de estas cuentas:

| Usuario | Contraseña | Para qué sirve |
|---|---|---|
| `beneficiario` | `Prototipo2026!` | Es Camila: consulta su saldo y movimientos, busca comercios y paga. |
| `beneficiario2` | `Prototipo2026!` | Es Diego: sirve para comprobar que nadie puede ver la cuenta de otra persona. |
| `sinmovimientos` | `Prototipo2026!` | Una cuenta nueva, sin operaciones, para ver cómo se muestra un historial vacío. |
| `administrador` | `AdminPluxee2026!` | Ve el panel de seguimiento, la bitácora, los usuarios, los comercios y los informes. |

El **PIN para pagar es `4826`**. Estas claves son públicas a propósito: son parte del ejercicio. Si alguien cambió una contraseña desde **Mi perfil** (o desde el menú del administrador), usa la nueva.

### Paso 6 (opcional). Comprueba que todo esté bien

Haz doble clic en **`verificar.cmd`**. Corre las 149 pruebas automáticas y te avisa si la cobertura baja de 80 %.

### Las próximas veces

Solo abre `iniciar.cmd`: arranca en segundos y tus datos siguen ahí. Para apagarlo, presiona `Ctrl+C` en su ventana. Si además quieres apagar MySQL: `.venv\Scripts\python.exe scripts\mysql_local.py detener`.

### Si algo sale mal

| Si ves esto… | Haz esto |
|---|---|
| «Se necesita Python 3.12 o superior» | Instala Python desde python.org marcando «Add python.exe to PATH» y vuelve a abrir `iniciar.cmd`. |
| «No se pudieron instalar las dependencias» | Revisa tu conexión a internet e inténtalo de nuevo. |
| «No fue posible descargar mysql-8.4.13-winx64.zip» | Descárgalo desde tu navegador (dev.mysql.com → MySQL Community Server → Archives → versión 8.4.13, Windows ZIP) y cópialo en la carpeta `.runtime\downloads`. Al iniciar, el programa revisa que sea el archivo correcto antes de usarlo. |
| «Los puertos locales 3307 y 13306 están ocupados» | Hay otro MySQL corriendo en tu computador. Ciérralo y vuelve a intentar. |
| Un error al abrir el puerto 8443 | Seguramente ya tienes otra ventana de `iniciar.cmd` abierta. Ciérrala (o reinicia el computador). |
| «La conexión no es privada», o en la ventana aparece «AVISO El navegador rechazó el certificado local» | Te falta el paso 4. Hazlo y vuelve a abrir el navegador. |

¿Quieres comprobar la conexión cifrada sin instalar el certificado? Puedes usar: `curl.exe --cacert .runtime/security/web_tls/Pluxee_Prototipo_Local.crt https://127.0.0.1:8443/ingresar/`.

---

## 2. Qué puedes hacer en el prototipo

Todo lo que ves sale de la base de datos MySQL, y el servidor revisa cada filtro y cada permiso. Un beneficiario solo puede ver y mover su propia cuenta.

### Como beneficiario

- **Entrar y mantener la sesión segura.** Si te equivocas varias veces con la contraseña, la cuenta se bloquea por un rato. Antes de que la sesión venza, te avisa. Y si la sesión se cerró justo mientras consultabas algo, al volver a entrar regresas a esa misma consulta, con tus filtros.
- **Crear tu cuenta.** Desde la pantalla de ingreso puedes registrarte como beneficiario: recibes una tarjeta, un PIN y un abono de bienvenida de $48.000 que aparece en tus movimientos.
- **Ver tu saldo y tus movimientos.** La tarjeta de saldo muestra el monto, si está actualizado y a qué hora se confirmó. Si el servicio se cae, no te muestra un error frío: te dice «Saldo sin actualizar» con el último valor conocido (o «Saldo no disponible» si todavía no hay uno) y te deja reintentar. Los movimientos se agrupan por día, con el total de cada día, y cada compra muestra el ícono de su comercio.
- **Buscar comercios.** Por nombre, código, categoría o comuna, y puedes guardar tus favoritos.
- **Pagar.** Hay cuatro formas: Pago Online, Pago QR, Clave Dinámica (un código de 4 dígitos que dura hasta 90 minutos y sirve para una sola compra) y tarjeta. Antes de confirmar puedes revisar el comercio, el monto y cómo quedaría tu saldo. Si por error confirmas dos veces, se cobra una sola vez.
- **Tu tarjeta y tu perfil.** Bloquea o activa tu tarjeta, cambia tu nombre o tu contraseña y revisa tus inicios de sesión y las sesiones abiertas.
- **Pedir ayuda.** Si algo falla, puedes reportarlo. Recibes un folio (que puedes copiar con un botón) para seguir el estado de tu reporte y leer la respuesta del administrador.
- **Notificaciones.** La campana te avisa de movimientos nuevos y de respuestas a tus reportes.

### Como administrador

- **Panel de seguimiento.** Indicadores de las últimas 24 horas: inicios de sesión rechazados, accesos sin permiso, sesiones vencidas y más. Cada uno trae un pequeño gráfico de su tendencia y te dice si subió o bajó respecto del día anterior. También muestra el estado de los servicios y las interrupciones recientes.
- **Bitácora.** Todo lo que pasa queda registrado. Puedes filtrarlo, ver el detalle de cada interrupción y descargarlo en CSV.
- **Reportes.** Recibes los reportes de los usuarios, les asignas prioridad y responsable, y los pasas de Recibido a En revisión y luego a Resuelto.
- **Usuarios.** Crear beneficiarios, buscarlos, ordenarlos y abrir su ficha: editar datos, asignar una contraseña temporal (que deben cambiar al entrar), bloquear la tarjeta, registrar un abono o desactivar el acceso. Desactivar no borra nada: el historial se conserva.
- **Comercios e informes.** Crear y editar comercios, y consultar los movimientos entre dos fechas, con un gráfico y descarga en CSV.
- **Parámetros.** Ajustar el abono de bienvenida, los intentos de ingreso antes del bloqueo, los minutos de inactividad y el monto máximo por compra, sin reiniciar el servidor. La bitácora guarda el valor anterior y el nuevo.

### Detalles de la experiencia

- **Apariencia.** Tema claro, oscuro o el del sistema, contraste, cantidad de movimiento y avatar. Se guarda en tu navegador.
- **Cada sección tiene su identidad.** Un color y una ilustración propios: beneficio, pagos, comercios, cuenta, ayuda, monitoreo, usuarios, informes y ajustes. El texto usa la fuente Manrope y los títulos, Raleway.
- **Pequeños gestos.** Inicio te saluda según la hora del día, la tarjeta de saldo brilla y se inclina levemente al pasar el mouse y los gráficos muestran el valor exacto de cada barra.
- **Atajos.** `Ctrl + K` abre un buscador de opciones, y hay un recorrido guiado opcional que puedes volver a abrir desde Apariencia.
- **Sin mareos.** Si prefieres menos movimiento, el botón «Pausar animaciones» del pie de página (o la opción de movimiento reducido de tu sistema) apaga todos los efectos.
- **Avisos que se entienden.** Los mensajes de éxito aparecen flotando y se van solos; los errores se quedan en la página hasta que los resuelvas.

---

## 3. Recorrido sugerido para la presentación

1. Entra como `beneficiario`, mira el saldo y revisa los movimientos.
2. Busca un comercio, márcalo como favorito y toca «Pagar aquí».
3. Paga un monto pequeño con el PIN `4826`, revisa el comprobante y fíjate en que aparezca el nuevo movimiento.
4. Bloquea la tarjeta y comprueba que un nuevo pago se rechaza sin cobrar nada. Después vuelve a activarla.
5. Abre otra ventana del navegador, con otro perfil, y entra como administrador. Con el beneficiario consulta el saldo; con el administrador provoca una interrupción del servicio; vuelve al beneficiario y reintenta. Verás el aviso «Saldo sin actualizar» con la hora del último valor confirmado. Restablece el servicio, consulta de nuevo y revisa en el panel cuánto duró la interrupción.
6. Intenta abrir el panel de administración con la cuenta del beneficiario: el sistema lo rechaza.

Mientras el servicio está interrumpido, el botón de reintento muestra una cuenta regresiva. Si alguien intenta saltársela con una solicitud directa, el servidor responde con HTTP 429 («demasiadas solicitudes»). Ese fue un error real que encontramos y corregimos (caso CF01), y está documentado en `beneficios/tests/EVIDENCIA_PRUEBAS.md`.

---

## 4. Cómo está construido

Elegimos un **desarrollo incremental**: primero el ingreso y la sesión, después las consultas, luego el seguimiento y, al final, los pagos, los comercios, los reportes y la gestión de usuarios. Cada etapa se construyó sobre la anterior y todas comparten los mismos usuarios, permisos y base de datos.

Usamos **Django**, que ya trae resueltas cosas delicadas: autenticación, sesiones, formularios, consultas seguras a la base de datos y protección CSRF. En el código, las vistas coordinan cada recorrido; `services.py` obtiene los datos; `responses.py` arma las respuestas según el caso; `events.py` avisa a la bitácora de lo que ocurre, y `policies.py` guarda reglas fijas, como los tiempos de sesión.

El saldo es simplemente abonos menos cargos. Cuando pagas, MySQL guarda el movimiento y el comprobante en una sola transacción y bloquea la cuenta mientras tanto, para que dos pagos simultáneos no se pisen. Si la bitácora no logra registrar el pago, el cobro se deshace. Además, cada parte del sistema entra a la base de datos con su propio usuario y solo con los permisos que necesita: la consulta de saldo solo puede leer, la aplicación escribe únicamente en lo suyo y la creación de tablas usa una credencial aparte.

¿Por qué MySQL? En la Evaluación 2 dejamos abierta la elección del motor (p. 64) y en un borrador pensamos en SQLite. Al implementarlo elegimos MySQL porque permite mostrar permisos distintos por usuario dentro del propio motor. SQLite lo seguimos usando para desarrollar y para las pruebas automáticas, porque es rápido y desechable.

### 4.1 Los tres servicios: qué entra, qué hace el servidor y qué sale

La guía pide al menos tres servicios que muestren claramente su entrada, su proceso y su resultado:

| Servicio | Qué entra | Qué hace el servidor | Qué obtienes |
|---|---|---|---|
| Consulta de saldo y movimientos | Tu sesión y los filtros de fecha y tipo | Revisa el tipo, el rango y el largo de los filtros; comprueba que la cuenta sea tuya y que el servicio esté disponible, y calcula el saldo (abonos menos cargos) con un usuario de solo lectura | El saldo con su hora de confirmación, los movimientos por día o un aviso claro si el servicio está interrumpido |
| Pago (QR, clave dinámica, online o tarjeta) | Comercio, monto y PIN o clave dinámica | Comprueba que la tarjeta esté activa, que te alcance el saldo, que no superes el monto máximo y que la clave siga vigente; guarda el cargo y el comprobante en una sola transacción | El comprobante, el nuevo movimiento y su registro en la terminal y en la bitácora |
| Reportes y seguimiento | Tipo y descripción del problema; luego, la respuesta y el estado que pone el administrador | Rechaza caracteres peligrosos, asigna un folio y un estado (Recibido → En revisión → Resuelto) y registra cada cambio | El folio y el estado de tu reporte, la respuesta del administrador y una bandeja con filtros para él |

### 4.2 Cómo se ordena el código

La guía propone una estructura de carpetas de ejemplo. Django organiza las cosas con otros nombres, pero la idea es la misma:

| En la guía | En este proyecto |
|---|---|
| `/src/controllers` | `beneficios/views*.py`: una vista por tema (usuarios, comercios, informes, parámetros, reportes) |
| `/src/models` | `beneficios/models.py`, `identidad/models.py` y las migraciones |
| `/src/services` | `beneficios/services.py` (consultas), `events.py` (bitácora), `responses.py` (respuestas) |
| `/src/utils` | `validators.py`, `charts.py`, `csv_export.py`, `receipt_pdf.py`, `parameters.py` |
| `/tests` | `beneficios/tests/`: 149 pruebas y la evidencia de cada corrección |
| `/docs` | `docs/` (revisión de código y guía de presentación) y este README |
| `/config` | `config/`: entornos de desarrollo, pruebas y producción, cifrado y HTTPS |

### 4.3 Principios SOLID y código limpio

- **Cada pieza hace una sola cosa.** Cada tema tiene sus propias vistas y formularios (`views_users.py`, `forms_users.py`, etc.), y la revisión de caracteres peligrosos vive en un único validador que usan todos los formularios.
- **Se puede ampliar sin romper lo que existe (patrón Factory Method).** `responses.py` define `ResponseCreator` con sus variantes «actualizada», «pendiente» y «rechazada». Si mañana necesitamos otro tipo de respuesta, se agrega una clase nueva sin tocar las vistas.
- **Las vistas no dependen de dónde vienen los datos (patrón Adapter).** Las consultas usan la interfaz `IBenefitServiceAdapter`. Hoy la implementa `MockDataServiceAdapter` con nuestra base académica, pero podría cambiarse por una fuente real sin modificar las vistas.
- **Interfaces pequeñas.** La interfaz de consulta solo pide dos cosas: `balance` y `movements`.
- **Avisar sin acoplar (patrón Observer).** `events.py` le avisa a la bitácora de cada evento, sin que las vistas sepan cómo se guarda.
- **Código limpio.** Nombres que se entienden, ninguna contraseña escrita en el código, ninguna lista de negocio fija en el código (las categorías y las preguntas de ayuda están en tablas) y una prueba automática por cada error corregido.

### 4.4 Decisiones que tomamos (y lo que nos costaron)

Toda decisión técnica tiene un costo. Estas son las principales:

| Decisión | Lo que ganamos | Lo que aceptamos a cambio |
|---|---|---|
| Django en vez de un framework mínimo | Autenticación, sesiones, CSRF, consultas seguras y salidas protegidas ya probadas | Un proyecto más grande |
| MySQL para la presentación, SQLite para desarrollar y probar | Permisos por usuario en el motor y pruebas rápidas | Los motores no son idénticos; encontramos una diferencia (CF05) y la corregimos |
| Montos y datos personales cifrados (AES-256-GCM) | Si alguien copia la base, no puede leerla | Los totales no se pueden sumar en SQL; se calculan en el servidor |
| Gráficos dibujados en el servidor | Cumplen la política de seguridad del sitio, que no permite scripts ni estilos incrustados | Son menos interactivos que los de una librería de gráficos |
| Bloqueo temporal tras varios intentos fallidos (configurable) | Frena a quien intenta adivinar contraseñas sin dejar cuentas inutilizables | Hay que esperar 15 minutos en vez de pedir que un administrador desbloquee |
| Desactivar en vez de borrar cuentas y comercios | Se conserva el historial y la bitácora (Ley N.º 21.459) | Los registros inactivos siguen en la base |
| Funcionar en tu computador con HTTPS | Se puede mostrar sin pagar servidores ni exponer datos en internet | No tiene una dirección pública |

Además, siempre que se puede, el sistema solo acepta valores de una **lista cerrada** (*whitelisting*): estados, categorías, tipos de movimiento, medios de pago y comercios tienen que ser una de las opciones definidas (`ChoiceField` y `ModelChoiceField`). El nombre de usuario solo admite letras sin tilde, números y `. _ @ -`.

---

## 5. Pruebas, entornos y entrega continua

`verificar.cmd` revisa el proyecto y corre las pruebas con su cobertura. `.venv\Scripts\python.exe scripts\entregar.py` hace eso mismo y además revisa las migraciones, prepara los archivos del sitio y arma el ZIP; si un paso falla, se detiene ahí. En `beneficios/tests/` están las pruebas, sus resultados y la evidencia de cada corrección.

Cada vez que subimos cambios a GitHub, **GitHub Actions** repite esta verificación automáticamente (`.github/workflows/verificacion.yml`). Ahí no se instala el cliente de MySQL porque las pruebas usan SQLite. El historial completo está en la pestaña **Actions** del repositorio público `YkzPam/prototipo-pluxee`, y la primera ejecución exitosa fue el 11 de noviembre de 2026.

La rama **`evaluacion-3`** es la entrega del prototipo. El informe de la Evaluación 4 irá en su propia rama, sin reemplazar esta. Para identificar exactamente lo entregado basta con la rama y el código (hash) del último commit.

También hay un despliegue local completo: `.venv\Scripts\python.exe scripts\entregar.py --desplegar`. Arma el ZIP verificado, prueba la versión nueva en otro puerto con HTTPS y MySQL y, solo si todo funciona, la pasa al puerto 8443. Los resultados quedan en `dist/verificacion_local.txt` y `dist/despliegue_local.json`.

### 5.1 El pipeline paso a paso (CI/CD)

Se ejecuta con una sola orden y se detiene en el primer paso que falla:

| Etapa | Qué se ejecuta | Para qué sirve |
|---|---|---|
| 1. Revisión general | `manage.py check` | Que la configuración y los modelos no tengan errores |
| 2. Pruebas | `coverage run manage.py test` | Que todas las pruebas pasen, en una base desechable |
| 3. Calidad mínima | `coverage report --fail-under=80` | Que la cobertura no baje de 80 % |
| 4. Migraciones | `makemigrations --check --dry-run` | Que los modelos y la base estén sincronizados |
| 5. Archivos del sitio | `collectstatic --noinput` | Que estilos, scripts e imágenes se puedan publicar |
| 6. Paquete | ZIP con comprobación de integridad | Que solo lleve código y documentación: nada de bases, claves ni certificados |
| 7. Versión candidata (`--desplegar`) | Se extrae en `.runtime/releases/<huella>` y se inicia en un puerto libre | Probar la versión nueva sin apagar la que está funcionando |
| 8. Revisión de la candidata | `scripts/verificar_https.py` sobre MySQL | HTTPS, cookies, CSRF, sesiones, permisos y un pago real sin duplicados |
| 9. Activación con respaldo | Reemplazo en el puerto 8443 | Si la nueva versión no responde, vuelve la anterior |

Las etapas 1 a 6 son las mismas que corre GitHub Actions. La revisión de código está en `docs/REVISION_CODIGO.md` y el guion de la presentación, en `docs/GUIA_PRESENTACION.md`.

### 5.2 Los tres entornos

| Entorno | Configuración | Para qué |
|---|---|---|
| Desarrollo | `config.settings.development` | Programar con SQLite y HTTP, solo en `127.0.0.1` |
| Pruebas | `config.settings.testing` | Correr las pruebas con una base en memoria que se borra al terminar |
| Demostración (producción) | `config.settings.production` | Presentar con MySQL, HTTPS, HSTS y cookies seguras |

En la demostración, las conexiones a MySQL también van cifradas y verifican el certificado del motor. La revisión automática del sitio usa el certificado local sin desactivar su validación.

Los datos sensibles se cifran con AES-256-GCM. Las contraseñas y el PIN primero se convierten en un hash y luego se cifra ese resultado. Las claves no están en el repositorio: quedan protegidas con DPAPI, el sistema de Windows que las ata a tu usuario. Un detalle honesto: separar los permisos en MySQL no aísla procesos que corren con ese mismo usuario de Windows. Los formularios usan CSRF y la bitácora nunca guarda contraseñas, PIN ni identificadores de sesión.

Sobre las pruebas de carga: un intento anterior con SQLite quedó interrumpido. Sus datos están en `beneficios/tests/perfil_carga_parcial.json`, pero no los usamos para afirmar nada sobre la versión con MySQL ni para decir que se completaron diez minutos de prueba.

---

## 6. Seguridad: qué revisamos y qué comprobamos

### 6.1 Controles y resultados

El 9 de noviembre de 2026 revisamos los permisos por perfil y por cuenta, los formularios de ingreso y consulta, el vencimiento de las sesiones y la configuración de HTTPS y MySQL. La tabla conecta los riesgos del OWASP Top 10:2021 que pide la guía con lo que hace el prototipo (OWASP Foundation, 2021). El control de acceso y el cifrado se relacionan con los controles de ISO/IEC 27002:2022 (International Organization for Standardization, 2022), dentro del alcance de lo que probamos en el entorno local.

| Riesgo o control | Cómo lo resolvimos | Cómo lo comprobamos |
|---|---|---|
| OWASP A01: control de acceso | `beneficios/security.py` exige iniciar sesión y revisa si eres administrador. `beneficios/views.py` busca la cuenta usando tu identidad. `beneficios/views_support.py` solo te muestra tus propios reportes. | Por HTTPS, el beneficiario recibió HTTP 403 al intentar entrar al panel de administración, y una sesión cerrada recibió HTTP 401 en la API. `test_workflows.py` prueba los intentos de ver otra cuenta y de entrar a la administración. |
| Autenticación y sesión | Django guarda solo el hash de la contraseña. `beneficios/security.py` limita los intentos fallidos y `beneficios/middleware.py` controla el vencimiento de la sesión y el cambio obligatorio de contraseñas temporales. | `test_lockout_rejects_even_correct_password_until_timeout` prueba el bloqueo. Por HTTPS creamos una cuenta con contraseña temporal: después de cambiarla se pudo entrar y la sesión anterior quedó invalidada (HTTP 401). `test_user_management.py` prueba que la clave restablecida por el administrador obliga a cambiarla (caso CF02). |
| OWASP A02: cifrado | `config/settings/production.py` activa HTTPS, HSTS y cookies seguras. `config/settings/database_secure.py` verifica la identidad de MySQL. `config/encrypted_fields.py` cifra los campos sensibles con AES-GCM y `config/vault.py` protege las claves con DPAPI. | La web y las dos conexiones a MySQL usaron TLS 1.3. La cookie de sesión salió con Secure, HttpOnly y SameSite=Lax. MySQL rechazó un intento de conexión sin cifrar (error 1045). |
| OWASP A03: inyección | Los formularios revisan el tipo, el rango y el largo de lo que escribes. `beneficios/validators.py` rechaza en todos los campos de texto los caracteres que indica la pauta (`< > " ' % ( ) & + \` y el carácter nulo). Las consultas usan el ORM de Django. Las categorías y las preguntas de ayuda vienen de tablas. La cuenta de consulta tiene permisos mínimos. | `test_input_validation_rejects_missing_oversized_and_injection_inputs` prueba entradas maliciosas. `test_owasp_inputs.py` prueba cada carácter en cada formulario. `test_invalid_filters_are_rejected_without_query_result` comprueba el HTTP 400. En MySQL, la cuenta de consulta recibió el error 1142 al intentar escribir o leer donde no le corresponde. |
| Operaciones protegidas y registro | El ingreso usa CSRF. El pago guarda el cargo y el comprobante en una sola transacción. La bitácora registra el resultado sin guardar credenciales. | Por HTTPS, un envío sin token recibió HTTP 403 y repetir el mismo pago generó un solo cargo. `test_database_audit_failure_rolls_back_payment_and_receipt_together` prueba que el cobro se deshace si falla la bitácora. |

**Dos errores reales que encontramos y corregimos:**

- **CF01.** Al principio, cuando el servicio estaba interrumpido, reintentar de inmediato devolvía HTTP 503 en vez de pedir que esperaras. Lo corregimos en `beneficios/views.py`: ahora la sesión se guarda antes del primer 503, así que el siguiente intento durante la espera recibe HTTP 429. La prueba reproduce la interrupción y comprueba que el saldo se recupera al restablecer el servicio. Detalles en el [registro de pruebas](beneficios/tests/EVIDENCIA_PRUEBAS.md).
- **Intentos simultáneos.** El contador de ingresos fallidos podía «perder» intentos si llegaban al mismo tiempo. En una prueba controlada con MySQL, el código antiguo registró solo 2 de 5 intentos. Ahora `beneficios/security.py` bloquea el registro mientras lo actualiza y reintenta si MySQL detecta un conflicto: se registraron los 5 intentos, y en otra prueba, 12 de 12 desde cuentas distintas. Estas pruebas se hicieron aparte de la suite automática.

**Leyes que consideramos.** Todo el prototipo usa datos inventados y funciona en un computador local. La Ley N.º 19.628 (1999, arts. 7 y 11) nos sirvió de guía para cuidar la reserva de los datos, y la Ley N.º 21.459 (2022, arts. 2 y 4), para pensar en el acceso indebido y la integridad de la información. Las pruebas de acceso denegado, los perfiles separados y la bitácora son la evidencia técnica, dentro de un alcance académico.

Para repetir estas comprobaciones con el prototipo encendido, desde la carpeta del proyecto:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\verificar_https.py
.\.venv\Scripts\python.exe -X utf8 scripts\mysql_local.py verificar
```

### 6.2 Cómo lo mostramos en la presentación

Empezamos explicando por qué elegimos un prototipo incremental: el acceso, las consultas y el seguimiento se sumaron por etapas sobre la misma base. Después entramos como beneficiario y mostramos los tres servicios completos. Para la parte de interfaz y experiencia, mostramos qué pasa cuando el servicio se cae: el aviso, el último saldo confirmado con su hora y cómo se recupera. Y en la vista móvil del navegador se puede ver que el menú, los avisos y los botones siguen funcionando.

| Servicio | Qué hacemos | Qué se ve |
|---|---|---|
| Consulta de saldo | Consultamos el saldo; desde otra ventana, el administrador interrumpe el servicio; reintentamos y, al terminar la espera, restablecemos el servicio | El saldo confirmado, el aviso «Saldo sin actualizar» y la recuperación. La duración de la interrupción aparece en el panel. |
| Consulta de movimientos | Elegimos un tipo de movimiento o un rango de fechas; el servidor revisa los filtros y busca solo en la cuenta propia | La lista filtrada, o un mensaje claro si en esas fechas no hubo movimientos |
| Pago | Elegimos Pago QR, escribimos el código de un comercio de prueba y confirmamos un monto con el PIN | El comprobante y el nuevo movimiento. Si se confirma dos veces, se cobra una sola |

Para cerrar, intentamos abrir el panel de administración con la cuenta del beneficiario, mostramos el rechazo y lo vemos registrado en la bitácora del administrador. Al cerrar sesión, el sistema pide volver a entrar para ver cualquier página protegida. Quien haya revisado el código puede repetir el caso CF01 y dejar registrado su nombre, la fecha, la versión revisada y el resultado.

La guía pide que el grupo defina un representante como interlocutor con el docente, y los pasos 1, 2 y 3 del prototipo se evalúan durante esta presentación.

---

## 7. Referencias

El diseño se inspira en las funciones públicas de la aplicación Pluxee Chile y en su manual para usuarios Junaeb. El código, el catálogo de comercios y todos los datos son nuestros e independientes: no copiamos promociones reales ni presentamos comercios inventados como si estuvieran adheridos.

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

Las fuentes **Raleway** y **Manrope** se incluyen en el proyecto bajo la licencia libre SIL Open Font License; sus licencias están en `static/fonts/OFL-Raleway.txt` y `static/fonts/OFL-Manrope.txt`.
