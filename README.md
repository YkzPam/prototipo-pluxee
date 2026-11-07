# Prototipo académico Pluxee Chile

Aplicación web funcional de la evaluación 3 de Ingeniería de Software. La evaluación 4 corresponde al informe de diagramas y pruebas. Este proyecto continúa el caso académico de consultas interrumpidas y cierres de sesión; no modifica ni se conecta a los sistemas reales de Pluxee.

## 1. Inicio en este equipo

1. Ejecutar `iniciar.cmd` dentro de esta carpeta.
2. Abrir **http://127.0.0.1:8765** en el navegador.
3. Mantener abierta la ventana del servidor durante la demostración. `Ctrl+C` lo detiene.

El entorno de este equipo ya está preparado. En otro equipo con Python 3.12 o superior, primero se debe ejecutar `preparar.cmd`; ese paso descarga las dependencias indicadas en `requirements.txt`. Los archivos de la base de datos y las claves se generan localmente; no se incluyen en el código compartido.

| Usuario de prueba | Función |
|---|---|
| `beneficiario` | Cuenta de Camila; saldo, movimientos, comercios y pago académico. |
| `beneficiario2` | Cuenta de Diego; permite comprobar la separación entre cuentas. |
| `sinmovimientos` | Cuenta sin operaciones; muestra un resultado vacío válido. |
| `administrador` | Bitácora y escenarios controlados de disponibilidad. |

La contraseña inicial de todas las cuentas es **`Prototipo2026!`**. El PIN de pago ficticio es **`4826`**. Son credenciales públicas del ejercicio, sin relación con servicios reales. Si se cambia una contraseña dentro de la demostración, volver a ejecutar la preparación conserva el cambio; no sobrescribe cuentas existentes.

## 2. Funciones disponibles

La navegación principal utiliza Inicio, Pagar, Comercios y Mi perfil. El saldo y los movimientos provienen de SQLite. Los filtros se comprueban en el servidor y las operaciones del beneficiario se limitan a su propia cuenta.

- **Acceso y sesión:** ingreso, rechazo genérico de credenciales, bloqueo temporal, continuidad al navegar, vencimiento y cierre que invalida la sesión anterior.
- **Saldo y movimientos:** consulta actualizada, filtros, historial vacío, interrupción diferenciada y reintento. Una falla no sustituye el saldo por cero.
- **Comercios:** catálogo ficticio, búsqueda por nombre o código, categoría, comuna y favoritos por usuario.
- **Pago académico:** selección del comercio, validación de monto y PIN, tarjeta activa, saldo suficiente, cargo persistido y comprobante privado. Repetir la misma confirmación conserva un único cargo.
- **Mi tarjeta y perfil:** bloqueo o activación de la tarjeta ficticia, edición del nombre de prueba y acceso al cambio de contraseña.
- **Seguimiento:** eventos y filtros para el administrador. Sus controles permiten interrumpir o restablecer las fuentes de saldo y movimientos sin alterar el libro de operaciones.

## 3. Recorrido para la presentación

1. Ingresar como `beneficiario`, consultar el saldo y revisar los movimientos.
2. Buscar un comercio, marcarlo como favorito y abrir «Pagar aquí».
3. Confirmar un monto de prueba con el PIN `4826`, revisar el comprobante y comprobar el nuevo movimiento.
4. Bloquear la tarjeta de prueba y comprobar que un nuevo pago sea rechazado sin generar un cargo. Activarla nuevamente.
5. Cerrar la sesión, ingresar como `administrador` e inducir una interrupción de saldo. Cerrar y entrar como beneficiario para observar la consulta pendiente y el reintento. Restablecer el servicio desde administración y repetir la consulta.
6. Mostrar el rechazo del panel administrativo al usar un beneficiario. La prueba automatizada también verifica intentos de consultar otra cuenta y de reutilizar una sesión cerrada.

## 4. Organización técnica

El modelo es incremental: acceso y sesión, consultas, seguimiento y funciones adicionales comparten usuarios, permisos y persistencia. Django controla autenticación, sesiones, formularios, ORM y CSRF. Las vistas coordinan el recorrido; `services.py` adapta los datos académicos; `responses.py` construye respuestas diferenciadas; `events.py` notifica el registro de eventos. `policies.py` conserva únicamente configuración inmutable por proceso, sin un usuario compartido.

El saldo se calcula como abonos menos cargos. El pago confirma el movimiento y el comprobante en una transacción, serializa la consulta del saldo y utiliza una referencia única por usuario. Una falla de auditoría obligatoria revierte el cargo. SQLite utiliza transacciones `IMMEDIATE`; esta decisión sirve para la demostración local y no acredita capacidad empresarial.

## 5. Verificación y entornos

`verificar.cmd` comprueba el proyecto y ejecuta las pruebas con cobertura. `python scripts/entregar.py` ejecuta la verificación, comprueba las migraciones, recopila los recursos y genera el ZIP; detiene el proceso si falla un paso. Los archivos de `beneficios/tests/` conservan casos, salidas y la evidencia de una corrección real. La configuración de integración continua está en `.github/workflows/verificacion.yml`; comprueba y prepara un paquete, pero su presencia no implica que GitHub Actions se haya ejecutado o que exista un despliegue remoto.

| Perfil | Configuración y alcance |
|---|---|
| Desarrollo local | `config.settings.development`; servidor ligado exclusivamente a `127.0.0.1`, datos sintéticos y HTTP local. |
| Pruebas | `config.settings.testing`; base de pruebas separada y descartable, mismas reglas de negocio. |
| Demostración HTTPS | `config.settings.production`; requiere clave externa de al menos 50 caracteres, hosts exactos y un servidor TLS con certificado válido. |

El perfil HTTPS activa cookies Secure, redirección a HTTPS y HSTS. La versión local abierta en este equipo utiliza HTTP de loopback: **no acredita todavía una presentación por HTTPS ni autorización de Pluxee**. Tampoco acredita la evaluación de comprensión con cinco participantes. SQLite no ofrece usuarios y roles propios del motor; los permisos de la aplicación no se presentan como sustituto de esa condición empresarial.

La verificación del paquete completó 53 pruebas con 95 % de cobertura del código Python seleccionado. El intento de carga de veinte usuarios quedó interrumpido: sus eventos persistidos y las condiciones de la interrupción están en `beneficios/tests/perfil_carga_parcial.json`. No se presenta ese intento como una prueba completa de diez minutos ni como medición del percentil 95 de latencia HTTP.

Los secretos no se guardan en el repositorio. Las contraseñas y el PIN se almacenan mediante hash. La sesión permanece en el servidor; no se utiliza almacenamiento web para credenciales. Los formularios conservan CSRF y las plantillas y el JavaScript tratan las salidas como texto. La bitácora excluye contraseñas, PIN e identificadores de sesión reutilizables.

## 6. Referencias del diseño y la implementación

La organización visual toma como referencia las funciones públicas de la aplicación Pluxee Chile y su manual Junaeb. La implementación, el catálogo y los datos del ejercicio son independientes; no se reproducen promociones vigentes ni se presentan comercios ficticios como adheridos reales.

- Pluxee Chile. (s. f.). [Pluxee App](https://www.pluxee.cl/productos/descarga-pluxee-app/).
- Pluxee Chile. (2026). [Manual guía usuario Junaeb](https://lp.pluxee.cl/hubfs/JUNAEB%202026/ARCHIVOS/2026_MANUAL%20GU%C3%8DA%20USUARIO.pdf).
- Django Software Foundation. (s. f.). [Security in Django](https://docs.djangoproject.com/en/5.2/topics/security/).
- Django Software Foundation. (s. f.). [How to use sessions](https://docs.djangoproject.com/en/5.2/topics/http/sessions/).
- Django Software Foundation. (s. f.). [SQLite: transactions behavior](https://docs.djangoproject.com/en/5.2/ref/databases/#transactions-behavior).

La fuente Raleway se distribuye localmente bajo SIL Open Font License; su licencia está en `static/fonts/OFL-Raleway.txt`.
