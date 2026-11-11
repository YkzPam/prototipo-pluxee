# Guía para la presentación del prototipo

La guía de la unidad indica que los pasos 1, 2 y 3 se evalúan durante la presentación. Esta secuencia recorre cada dimensión de la rúbrica del prototipo: interfaz, experiencia de usuario, desarrollo según la guía y OWASP, y corrección del código a partir de las pruebas.

## 1. Preparación (el día anterior)

1. **Cerrar versiones anteriores.** Reiniciar el equipo o cerrar cualquier ventana de `iniciar.cmd` abierta: el puerto 8443 debe quedar libre. Alternativa sin reiniciar: `.venv\Scripts\python.exe scripts\entregar.py --desplegar` prueba la versión nueva en otro puerto y, si pasa la verificación, reemplaza la que está en el 8443.
2. **Iniciar el prototipo.** Ejecutar `iniciar.cmd` y esperar el mensaje `Prototipo académico Pluxee Chile: https://127.0.0.1:8443/`. Mantener la ventana abierta.
3. **Confiar en el certificado local** (una sola vez por equipo, para que el navegador no muestre la advertencia «La conexión no es privada»):
   1. Abrir la carpeta `.runtime\security\web_tls\` del proyecto.
   2. Doble clic en `Pluxee_Prototipo_Local.crt` → **Instalar certificado…** → **Usuario actual** → Siguiente.
   3. Elegir **Colocar todos los certificados en el siguiente almacén** → **Examinar…** → **Entidades de certificación raíz de confianza** → Aceptar → Siguiente → Finalizar.
   4. Aceptar la advertencia de seguridad de Windows y cerrar y volver a abrir el navegador.
   5. Abrir `https://127.0.0.1:8443/`: el candado debe aparecer sin advertencias.

   El certificado solo es válido para `localhost` y `127.0.0.1`. Para retirarlo después: `certmgr.msc` → Entidades de certificación raíz de confianza → Certificados → «Prototipo Pluxee local» → Eliminar.
4. **Comprobar en dos minutos:** `verificar.cmd` (pruebas) y, con el sitio iniciado, `.venv\Scripts\python.exe -X utf8 scripts\verificar_https.py`.
5. **Navegadores:** una ventana normal para el beneficiario y otra de perfil distinto (o de incógnito) para el administrador, porque las sesiones son independientes.

| Cuenta | Contraseña | Uso |
|---|---|---|
| `beneficiario` | `Prototipo2026!` | Camila Rojas: saldo, movimientos, pagos |
| `beneficiario2` | `Prototipo2026!` | Diego Muñoz: separación entre cuentas |
| `administrador` | `AdminPluxee2026!` | Panel, bitácora, usuarios, comercios, parámetros |
| PIN de pago | `4826` | Pagos y clave dinámica |

## 2. Paso 1: modelo de prototipo (1 minuto)

- Modelo **incremental**: acceso y sesión → consultas de saldo y movimientos → seguimiento administrativo → pagos, comercios, reportes, gestión de usuarios y parámetros. Cada incremento comparte usuarios, permisos y base de datos.
- Arquitectura: Django (vistas, formularios, ORM, sesiones y CSRF), MySQL con cuentas separadas por nivel de confianza y HTTPS local. Justificación en el README, sección 4.

## 3. Paso 2: interfaz y experiencia de usuario (3 minutos)

| Condición de la pauta | Qué mostrar |
|---|---|
| Diseño claro con reglas de estilo | Encabezados, colores y botones coherentes en todas las secciones |
| Flexible / responsive | Herramientas del navegador → vista móvil: menú inferior, tarjetas y tablas se adaptan |
| Elementos familiares y fáciles | Accesos rápidos de Inicio; buscador con `Ctrl + K` |
| Eficiencia | Pagar desde un comercio con «Ir al pago»; favoritos que conservan la posición |
| Jerarquía visual | Saldo destacado, resúmenes y luego el detalle |
| Contenido que guía | Mensajes de error junto al campo, avisos flotantes al guardar, recorrido guiado |
| Accesibilidad | Apariencia: tema oscuro, mayor contraste y movimiento reducido; navegación con teclado |
| Emociones del usuario | Interrupción de saldo: se muestra el último saldo confirmado en vez de un error o un saldo cero |

## 4. Paso 3: los tres servicios con entrada, proceso y resultado (5 minutos)

1. **Consulta de saldo.** Entrada: solicitud del beneficiario. Proceso: el servidor suma abonos y resta compras de la cuenta autenticada. Resultado: saldo con la hora de confirmación.
2. **Consulta de movimientos.** Entrada: filtros de fecha y tipo. Proceso: validación en el servidor y consulta parametrizada. Resultado: historial agrupado por día y detalle de cada movimiento.
3. **Pago.** Entrada: comercio (o código QR), monto y PIN. Proceso: verificación del comercio, la tarjeta, el saldo y el monto máximo configurado; un único cargo aunque se repita la confirmación. Resultado: comprobante, descarga en PDF, nuevo movimiento y notificación.
4. **Interrupción y recuperación** (con las dos ventanas): administrador → Seguimiento → «Inducir interrupción» en Saldo; beneficiario → «Actualizar saldo» muestra «Saldo sin actualizar»; administrador → «Restablecer servicio»; beneficiario → reintenta y recupera el saldo. La interrupción queda en el historial y en la Bitácora.

## 5. Seguridad y normativa que el docente puede verificar (4 minutos)

| Punto de la pauta | Demostración en vivo |
|---|---|
| Rechazo de caracteres peligrosos | Reportar un problema con `El saldo (no) cambió & <b>` → «No se admiten los caracteres…» |
| Contraseña oculta y compleja | Campo `type=password`; crear usuario con `abc` → rechazada |
| Bloqueo tras intentos fallidos | 5 ingresos erróneos → el correcto también se rechaza durante 15 minutos (umbral en Parámetros) |
| Clave temporal | Administrador → Usuarios → ficha → «Restablecer contraseña»; el usuario debe cambiarla al ingresar |
| Roles y privilegios | Beneficiario abre `https://127.0.0.1:8443/seguimiento/` → «Acceso restringido» (HTTP 403) |
| Sesión | Cierre de sesión en todas las páginas; inactividad configurable; «Cerrar otras sesiones» en Mi perfil |
| TLS | Candado del navegador; cookies Secure y HttpOnly |
| Cifrado y credenciales | Campos sensibles cifrados con AES-256-GCM; claves y contraseñas de MySQL fuera del código, protegidas con DPAPI |
| Credenciales por nivel de confianza | Cuenta de aplicación, cuenta de solo lectura y cuenta de aprovisionamiento (`scripts/mysql_local.py`) |
| Listas desde tablas | Categorías de comercio y preguntas de Ayuda vienen de la base de datos |
| Ley N.º 21.459 (auditoría) | Bitácora: filtros, detalle de cada evento y descarga CSV; cada cambio de parámetros registra valor anterior y nuevo |

## 6. Corrección del código a partir de las pruebas (2 minutos)

- Mostrar `beneficios/tests/EVIDENCIA_PRUEBAS.md`: cinco hallazgos reales (CF01 a CF05), cada uno con su causa, corrección y prueba.
- Mostrar `docs/REVISION_CODIGO.md`: lista de verificación y tabla de hallazgos.
- Ejecutar `verificar.cmd` o mostrar `dist/verificacion_local.txt`: 137 pruebas correctas y 87 % de cobertura.
- Pipeline CI/CD: README sección 5.1. Ejecutar `entregar.py --desplegar` antes de la exposición deja en `dist/despliegue_local.json` la evidencia del despliegue de esta versión (huella del ZIP, verificación del candidato y activación).

## 7. Preguntas probables

- **¿Por qué se desactivan cuentas y comercios en vez de eliminarlos?** Para conservar la trazabilidad de la bitácora y el historial de movimientos.
- **¿Qué pasa si se cae la base de datos o un servicio?** La consulta queda pendiente, se muestra el último dato confirmado, se limita el reintento (HTTP 429) y la interrupción queda registrada.
- **¿Cómo se evita un cobro duplicado?** Cada pago tiene una referencia única por usuario; repetir la confirmación devuelve el mismo comprobante.
- **¿Los datos son reales?** No: cuentas, comercios y montos son ficticios y el prototipo no se conecta a Pluxee.
