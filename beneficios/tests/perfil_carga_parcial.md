# Perfil de carga interrumpido

La ejecución iniciada el 6 de noviembre de 2026 utilizó un servidor Waitress en `127.0.0.1:8767` y una base SQLite independiente de la demostración principal. El perfil previsto comprendía veinte usuarios ficticios, una consulta por usuario cada cinco segundos durante seiscientos segundos y alternancia entre saldo y movimientos. No se probaron los servicios reales de Pluxee ni una conexión HTTPS. El proceso no dejó un cierre verificable ni el archivo final de muestras HTTP del cliente; esta evidencia corresponde a la recuperación parcial realizada el 7 de noviembre.

La base de datos conserva veinte eventos de inicio de sesión correcto y 1.620 eventos de consultas clasificadas como correctas por el servidor: 820 consultas de saldo y 800 de movimientos. Cada uno de los veinte usuarios registra 81 consultas. La primera consulta aparece a las 22:58:53.631362 UTC del 6 de noviembre y la última a las 23:05:33.955665 UTC de esa fecha. La separación entre ambos registros es de 400,324303 segundos; ese intervalo observado no acredita la ventana completa de seiscientos segundos.

Los registros de auditoría no sustituyen los resultados del cliente HTTP. Las latencias de extremo a extremo permanecían en memoria y no se recuperaron. No corresponde calcular ni afirmar el percentil 95 HTTP, una tasa total de éxito del perfil o el cumplimiento completo de RNF01 y RNF02 a partir de estos eventos parciales. El archivo JSON adjunto conserva el detalle por tipo de evento y cuenta, identifica estas limitaciones y distingue los tiempos internos del servidor de los tiempos HTTP que no están disponibles.

La revisión de recuperación encontró ausentes el proceso original y el servicio del puerto 8767. El servidor principal del puerto 8765 y su base de demostración se conservaron. No se atribuye la interrupción a una causa técnica específica porque no existe evidencia suficiente para hacerlo. Los avisos de profundidad de cola de Waitress muestran solicitudes en espera durante las ráfagas, pero por sí solos no permiten afirmar fallos del servicio ni explicar el cierre del proceso.

El script `scripts/perfil_carga.py` queda disponible para repetir el perfil completo en otra oportunidad. Ahora guarda cada muestra HTTP en un archivo NDJSON y actualiza un punto de control cada treinta segundos, con el fin de conservar resultados parciales si ocurre otro cierre externo. Esa mejora no recupera las muestras de la ejecución anterior y no se ha utilizado para presentar una nueva medición como realizada.

Para una nueva ejecución local, desde la carpeta del proyecto:

```cmd
.venv\Scripts\python.exe scripts\perfil_carga.py
```

El comando crea otra base exclusiva de prueba, utiliza por defecto el puerto 8767 y conserva las cuentas y registros de la demostración principal. El resultado solo debe considerarse completo cuando el JSON marque `status: completed`, contenga las 2.400 consultas esperadas y permita revisar sus muestras y duración. La evidencia de esta ejecución parcial se encuentra en `perfil_carga_parcial.json`.
