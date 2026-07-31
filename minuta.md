
# MINUTA DE DESARROLLO

## AegisWiFi — Plataforma profesional de auditoría de redes inalámbricas

**Versión:** 1.0
**Estado:** Planificación inicial
**Plataforma principal:** Kali Linux
**Tipo de aplicación:** Plataforma local de auditoría Wi-Fi
**Backend:** Python 3.13 + FastAPI
**Frontend:** React + TypeScript
**Base de datos inicial:** SQLite
**Motor de trabajos:** Cola asíncrona persistente
**Uso previsto:** Redes propias, laboratorios y auditorías expresamente autorizadas

---

# 1. Resumen ejecutivo

AegisWiFi será una plataforma profesional para ejecutar auditorías de seguridad sobre redes inalámbricas desde Kali Linux.

El sistema centralizará en una única aplicación las tareas de:

* Detección de interfaces inalámbricas.
* Activación y restauración del modo monitor.
* Descubrimiento de puntos de acceso y clientes.
* Clasificación de WPA, WPA2, WPA3, WPS y 802.1X.
* Captura y validación de handshakes EAPOL.
* Captura y validación de PMKID.
* Conversión de evidencias a formatos compatibles.
* Auditoría autorizada de contraseñas WPA2.
* Integración con Hashcat.
* Evaluación de WPS.
* Evaluación de PMF.
* Revisión de WPA3 y Transition Mode.
* Auditoría de redes WPA-Enterprise.
* Validación de segmentación y aislamiento.
* Detección de puntos de acceso fraudulentos.
* Conservación de evidencias.
* Generación de informes técnicos y ejecutivos.

La plataforma no será solamente una interfaz para herramientas existentes. Tendrá un motor propio encargado de:

* Controlar el alcance autorizado.
* Decidir qué acciones pueden ejecutarse.
* Coordinar procesos externos.
* Interpretar resultados.
* Correlacionar evidencias.
* Generar hallazgos.
* Calcular severidad.
* Proponer remediaciones.
* Conservar trazabilidad completa.

El cracking autorizado de redes WPA2 será una función central, pero estará integrado dentro de un proceso formal de auditoría.

---

# 2. Visión del producto

AegisWiFi debe convertirse en una plataforma equivalente a un escáner de vulnerabilidades especializado en infraestructura inalámbrica.

El operador deberá poder crear una auditoría, definir los objetivos permitidos y ejecutar un flujo completo sin tener que coordinar manualmente múltiples terminales, archivos PCAP, conversiones y procesos de cracking.

El resultado final de una auditoría deberá responder:

* Qué redes fueron detectadas.
* Cuáles estaban dentro del alcance.
* Qué tecnologías de seguridad utilizaban.
* Qué configuraciones inseguras fueron identificadas.
* Qué evidencias fueron capturadas.
* Si fue posible validar la fortaleza de la contraseña.
* Qué método fue utilizado.
* Qué impacto representa el hallazgo.
* Cómo debe corregirse.
* Qué herramientas y versiones participaron.
* Qué acciones activas fueron ejecutadas.
* Qué archivos respaldan cada conclusión.

---

# 3. Objetivos generales

## 3.1 Objetivo principal

Desarrollar una plataforma modular, extensible y segura para ejecutar auditorías inalámbricas completas desde Kali Linux.

## 3.2 Objetivos secundarios

* Automatizar la preparación de interfaces.
* Reducir errores manuales durante las auditorías.
* Centralizar capturas, hashes, logs y reportes.
* Integrar herramientas reconocidas de Kali Linux.
* Proporcionar una experiencia gráfica moderna.
* Permitir automatización mediante CLI y API.
* Soportar trabajos de larga duración.
* Mantener registros verificables de cada acción.
* Proteger credenciales y resultados sensibles.
* Permitir ampliar la plataforma con nuevos módulos.

---

# 4. Alcance funcional

## 4.1 Funciones incluidas

La primera versión completa deberá incluir:

1. Gestión de auditorías.
2. Definición de alcance.
3. Gestión de interfaces inalámbricas.
4. Comprobación del hardware.
5. Modo monitor.
6. Pruebas de inyección controladas.
7. Escaneo pasivo.
8. Inventario de AP.
9. Inventario de clientes.
10. Identificación de cifrado.
11. Análisis WPA2.
12. Análisis WPA3.
13. Análisis WPS.
14. Análisis PMF.
15. Captura EAPOL.
16. Captura PMKID.
17. Validación de handshakes.
18. Conversión a formato Hashcat.
19. Planificación de cracking.
20. Ejecución de Hashcat.
21. Gestión de diccionarios.
22. Gestión de reglas.
23. Gestión de máscaras.
24. Ataques híbridos autorizados.
25. Control de temperatura y recursos.
26. Protección de resultados.
27. Auditoría WPA-Enterprise.
28. Detección de rogue AP.
29. Evaluación de segmentación.
30. Evaluación de aislamiento.
31. Registro de evidencias.
32. Motor de hallazgos.
33. Informes HTML.
34. Informes PDF.
35. Exportación JSON.
36. CLI.
37. API local.
38. Panel web.
39. Sistema persistente de trabajos.
40. Restauración segura del sistema.

## 4.2 Funciones futuras

Se planifican como extensiones:

* FragAttacks.
* SSID Confusion.
* AirSnitch.
* Fuzzing WPA3-SAE.
* Wi-Fi 6E.
* Wi-Fi 7.
* Multi-Link Operation.
* Sensores remotos.
* Gestión multioperador.
* PostgreSQL.
* Servidor central.
* Integración con agentes de inteligencia artificial.
* Comparación histórica entre auditorías.
* Integración con sistemas de tickets.
* Integración con plataformas de gestión de vulnerabilidades.

---

# 5. Límites del producto

AegisWiFi no deberá:

* Ejecutar acciones activas fuera del alcance definido.
* Atacar automáticamente redes detectadas.
* Ejecutar deauthentication continuo.
* Probar contraseñas sin autorización.
* Guardar claves en texto plano sin protección.
* Transmitir evidencias a servicios externos.
* Exponer la API fuera de localhost por defecto.
* Ejecutar pruebas disruptivas automáticamente.
* Reemplazar el criterio profesional del auditor.
* Concluir que una contraseña es segura solo porque no fue recuperada.
* Modificar permanentemente interfaces sin poder restaurarlas.
* Descargar automáticamente colecciones de credenciales.
* Incorporar funciones de persistencia sobre dispositivos auditados.

---

# 6. Tipos de auditoría

## 6.1 Auditoría pasiva

No transmite tramas.

Permitirá:

* Detectar redes.
* Detectar clientes.
* Capturar beacons.
* Capturar probe responses.
* Analizar capacidades.
* Detectar EAPOL observado.
* Identificar PMKID observado.
* Detectar WPS.
* Analizar PMF.
* Identificar WPA3 Transition Mode.
* Detectar configuraciones heredadas.
* Analizar canales.
* Detectar anomalías.
* Identificar posibles rogue AP.

Será el modo predeterminado.

## 6.2 Auditoría activa controlada

Permitirá acciones limitadas:

* Prueba de inyección.
* Asociación controlada.
* Solicitud limitada de reconexión.
* Enumeración WPS.
* Validación de PMF.
* Prueba de aislamiento.
* Captura activa autorizada.
* Rogue AP sobre dispositivos controlados.

Cada acción deberá validarse contra el alcance.

## 6.3 Auditoría disruptiva de laboratorio

Permitirá:

* FragAttacks.
* Fuzzing WPA3-SAE.
* Evil Twin.
* Pruebas avanzadas de aislamiento.
* SSID Confusion.
* Pruebas de resiliencia.
* Simulación de fallos.
* Pruebas sobre firmware.

Este modo estará desactivado por defecto.

---

# 7. Flujo completo de una auditoría

```text
Crear engagement
        ↓
Registrar cliente y operador
        ↓
Cargar autorización
        ↓
Definir SSID y BSSID permitidos
        ↓
Configurar permisos
        ↓
Verificar interfaces
        ↓
Preparar modo monitor
        ↓
Ejecutar descubrimiento
        ↓
Clasificar redes y clientes
        ↓
Seleccionar objetivos autorizados
        ↓
Ejecutar auditoría pasiva
        ↓
Capturar EAPOL o PMKID
        ↓
Validar evidencia
        ↓
Generar archivo 22000
        ↓
Crear plan de cracking
        ↓
Ejecutar auditoría de contraseña
        ↓
Ejecutar pruebas complementarias
        ↓
Generar hallazgos
        ↓
Revisar evidencias
        ↓
Generar informe
        ↓
Restaurar interfaces
        ↓
Cerrar engagement
```

---

# 8. Arquitectura general

## 8.1 Capas

```text
┌────────────────────────────────────────────┐
│              Interfaz React                │
├────────────────────────────────────────────┤
│          REST API y WebSocket              │
├────────────────────────────────────────────┤
│ Engagements, Scope, Findings, Reports      │
├────────────────────────────────────────────┤
│            Motor de auditoría              │
├────────────────────────────────────────────┤
│ Motor de políticas y autorización          │
├────────────────────────────────────────────┤
│ JobManager, Queue y Supervisor             │
├────────────────────────────────────────────┤
│ Adaptadores de herramientas externas       │
├────────────────────────────────────────────┤
│ Linux, nl80211, mac80211, GPU y procesos   │
└────────────────────────────────────────────┘
```

## 8.2 Componentes principales

### Frontend

Responsable de:

* Mostrar estado de interfaces.
* Visualizar redes.
* Mostrar clientes.
* Crear auditorías.
* Configurar alcance.
* Iniciar trabajos.
* Mostrar progreso.
* Revisar evidencias.
* Consultar hallazgos.
* Generar informes.

### Backend

Responsable de:

* Exponer API.
* Aplicar permisos.
* Gestionar trabajos.
* Ejecutar adaptadores.
* Interpretar resultados.
* Persistir datos.
* Proteger secretos.
* Generar reportes.

### Motor de políticas

Responsable de autorizar o bloquear cada acción.

### Sistema de trabajos

Responsable de ejecutar procesos de corta y larga duración.

### Adaptadores

Responsables de interactuar con herramientas externas.

### Motor de hallazgos

Responsable de transformar evidencia técnica en vulnerabilidades documentadas.

---

# 9. Stack tecnológico

## 9.1 Backend

* Python 3.13.
* FastAPI.
* Uvicorn.
* Pydantic.
* SQLAlchemy.
* Alembic.
* SQLite.
* PostgreSQL opcional.
* Typer.
* asyncio.
* Psutil.
* Pyroute2.
* Scapy.
* Structlog.
* Cryptography.
* Jinja2.

## 9.2 Frontend

* React.
* TypeScript.
* Vite.
* Tailwind CSS.
* TanStack Query.
* Zustand.
* React Router.
* Recharts.
* WebSocket.
* Zod.

## 9.3 Herramientas integradas

* iw.
* iproute2.
* rfkill.
* Aircrack-ng.
* hcxdumptool.
* hcxtools.
* Hashcat.
* Kismet.
* Tshark.
* Wireshark.
* Reaver.
* Bully.
* Pixiewps.
* EAPHammer.
* hostapd.
* hostapd-wpe.
* Nmap.

---

# 10. Estructura inicial del repositorio

```text
aegiswifi/
├── README.md
├── LICENSE
├── pyproject.toml
├── package.json
├── Makefile
├── install.sh
├── uninstall.sh
├── config.example.yaml
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── core/
│   │   ├── engagements/
│   │   ├── scope/
│   │   ├── hardware/
│   │   ├── discovery/
│   │   ├── handshake/
│   │   ├── cracking/
│   │   ├── wireless_tests/
│   │   ├── traffic/
│   │   ├── adapters/
│   │   ├── jobs/
│   │   ├── evidence/
│   │   ├── findings/
│   │   ├── reporting/
│   │   └── database/
│   └── tests/
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── features/
│   │   ├── stores/
│   │   ├── hooks/
│   │   ├── api/
│   │   └── types/
│   └── tests/
│
├── rules/
│   ├── wireless/
│   ├── cracking/
│   ├── password/
│   └── reporting/
│
├── report_templates/
├── wordlists/
├── migrations/
├── scripts/
├── docs/
├── lab/
└── tests/
```

---

# 11. Módulo de engagements

## Objetivo

Gestionar cada auditoría como una entidad independiente.

## Datos requeridos

* Identificador.
* Nombre.
* Cliente.
* Operador.
* Fecha de inicio.
* Fecha de finalización.
* Estado.
* Documento de autorización.
* Notas.
* Permisos.
* Límites.
* Objetivos.

## Estados

```text
DRAFT
READY
ACTIVE
PAUSED
COMPLETED
CANCELLED
ARCHIVED
```

## Reglas

* Solo un engagement activo por interfaz.
* Un trabajo no puede iniciarse sin engagement.
* Los objetivos deben pertenecer al alcance.
* Las acciones activas requieren permisos específicos.
* Un engagement vencido no puede ejecutar trabajos.
* El cierre debe detener trabajos y restaurar interfaces.

---

# 12. Módulo de alcance y autorización

## Objetivo

Impedir que la aplicación ejecute pruebas fuera del ámbito permitido.

## Alcance configurable

* SSID autorizados.
* BSSID autorizados.
* Clientes autorizados.
* Canales.
* Bandas.
* Horarios.
* Tipo de pruebas.
* Duración máxima.
* Cantidad máxima de tramas activas.
* Tiempo máximo de cracking.
* Temperatura máxima.
* Pruebas Enterprise.
* Pruebas disruptivas.

## Archivo de alcance

```yaml
engagement:
  id: ENG-2026-001
  client: Laboratorio autorizado
  operator: Operador principal
  valid_from: 2026-07-29T08:00:00-03:00
  valid_until: 2026-07-29T18:00:00-03:00

scope:
  allowed_ssids:
    - LAB-WPA2
    - LAB-WPA3

  allowed_bssids:
    - AA:BB:CC:DD:EE:FF

permissions:
  passive_capture: true
  handshake_capture: true
  pmkid_capture: true
  controlled_reconnect: true
  password_audit: true
  wps_testing: true
  enterprise_testing: false
  denial_of_service: false
  protocol_fuzzing: false

limits:
  maximum_active_frames: 4
  maximum_cracking_duration_minutes: 120
  maximum_gpu_temperature: 78
```

## Validaciones previas

Antes de ejecutar una acción:

1. Engagement activo.
2. Fecha válida.
3. Operador autorizado.
4. Objetivo incluido.
5. Acción permitida.
6. Interfaz compatible.
7. Límite no agotado.
8. Canal válido.
9. Kill switch operativo.
10. Espacio en disco suficiente.

---

# 13. Módulo de hardware

## Objetivo

Detectar y preparar adaptadores Wi-Fi.

## Funciones

* Listar interfaces.
* Mostrar chipset.
* Mostrar driver.
* Mostrar PHY.
* Mostrar MAC.
* Mostrar bandas.
* Mostrar canales.
* Mostrar modos disponibles.
* Comprobar monitor mode.
* Comprobar AP mode.
* Comprobar inyección.
* Detectar bloqueo.
* Detectar procesos conflictivos.
* Crear interfaz monitor virtual.
* Restaurar configuración.

## Información mostrada

```text
Interfaz: wlan1
PHY: phy1
Chipset: MediaTek MT7612U
Driver: mt76x2u
Bandas: 2.4 GHz / 5 GHz
Monitor: compatible
Inyección: compatible
AP mode: compatible
Estado: disponible
```

## Criterios de aceptación

* La aplicación detecta interfaces sin intervención manual.
* Puede crear una interfaz monitor.
* No elimina la interfaz administrada si no es necesario.
* Registra el estado original.
* Puede restaurar completamente el estado anterior.
* Detecta desconexiones físicas.
* Detiene trabajos afectados.

---

# 14. Módulo de descubrimiento

## Objetivo

Mantener un inventario en tiempo real del entorno inalámbrico.

## Datos por AP

* SSID.
* BSSID.
* Canal.
* Frecuencia.
* Banda.
* Potencia.
* Fabricante.
* WPA.
* WPA2.
* WPA3.
* AKM.
* Cifrados.
* PMF.
* WPS.
* Transition Mode.
* Clientes.
* Primera detección.
* Última detección.
* Estado dentro o fuera de alcance.

## Datos por cliente

* Dirección MAC.
* MAC aleatoria.
* Fabricante probable.
* AP asociado.
* Señal.
* Probe requests.
* Primera detección.
* Última detección.
* Cliente controlado.
* Cliente autorizado.

## Funciones

* Channel hopping.
* Fijación de canal.
* Filtrado por SSID.
* Filtrado por BSSID.
* Filtrado por banda.
* Filtrado por alcance.
* Historial de cambios.
* Detección de AP duplicados.
* Detección de seguridad degradada.
* Exportación de inventario.

---

# 15. Módulo de handshake

## Objetivo

Capturar y validar material EAPOL utilizable en auditorías WPA2.

## Métodos de captura

* Captura pasiva.
* Captura dirigida por BSSID.
* Captura dirigida por cliente.
* Captura durante roaming.
* Captura mediante reconexión controlada.
* Importación de PCAP o PCAPNG.

## Elementos analizados

* M1.
* M2.
* M3.
* M4.
* Replay Counter.
* ANonce.
* SNonce.
* MIC.
* Key Descriptor.
* BSSID.
* Cliente.
* SSID.
* Canal.
* Marcas de tiempo.

## Estados

```text
NO_EVIDENCE
PARTIAL
USABLE
COMPLETE
INVALID
MIXED_CLIENTS
REPLAY_MISMATCH
PACKET_LOSS
CONVERSION_READY
```

## Calidad

* Excelente.
* Buena.
* Aceptable.
* Deficiente.
* Inválida.

## Criterios de aceptación

* Identificar correctamente AP y cliente.
* Detectar pares utilizables.
* Rechazar capturas mezcladas.
* Detectar inconsistencias de replay.
* Guardar PCAPNG original.
* Crear hash SHA-256.
* Convertir a formato compatible.
* Asociar evidencia a un engagement.

---

# 16. Módulo PMKID

## Objetivo

Detectar, validar y almacenar PMKID utilizable.

## Funciones

* Detectar PMKID en capturas.
* Validar estructura.
* Detectar PMKID cero.
* Eliminar duplicados.
* Correlacionar SSID y BSSID.
* Convertir a formato 22000.
* Registrar origen.
* Calcular calidad.
* Asociar con una red autorizada.

## Estados

```text
NOT_FOUND
CANDIDATE
VALID
INVALID
ZERO_VALUE
DUPLICATE
CONVERSION_READY
```

---

# 17. Módulo de conversión

## Objetivo

Transformar evidencia capturada en archivos compatibles con motores de auditoría.

## Entradas

* PCAP.
* PCAPNG.
* Capturas de Kismet.
* Capturas de Airodump-ng.
* Capturas de hcxdumptool.

## Salidas

* Archivo 22000.
* Resumen de EAPOL.
* Resumen de PMKID.
* Metadatos JSON.
* Resultado de validación.

## Requisitos

* Conservar archivo original.
* No sobrescribir evidencias.
* Calcular hashes.
* Registrar herramienta y versión.
* Registrar comando normalizado.
* Verificar que la salida no esté vacía.
* Detectar entradas duplicadas.

---

# 18. Motor de cracking autorizado

## Objetivo

Evaluar la fortaleza de contraseñas WPA2 mediante Hashcat.

## Estrategias

### Diccionario

* Listas comunes.
* Diccionarios proporcionados.
* Diccionarios regionales.
* Diccionarios corporativos autorizados.
* Contraseñas de laboratorio.

### Reglas

* Cambio de mayúsculas.
* Agregado de números.
* Agregado de años.
* Agregado de símbolos.
* Sustituciones comunes.
* Patrones organizacionales.

### Máscaras

* Formatos predecibles.
* Longitudes acotadas.
* Patrones numéricos.
* Combinaciones alfanuméricas.
* Espacios de claves limitados.

### Híbridos

* Palabra más sufijo.
* Prefijo más palabra.
* Organización más año.
* Localidad más número.
* Marca más símbolo.

### Generación contextual

Solo utilizará datos introducidos por el auditor:

* Nombre de organización.
* Localidades.
* Sucursales.
* Marcas.
* Años.
* Convenciones.
* Patrones históricos.
* Política declarada.

## Plan de cracking

Cada trabajo deberá definir:

* Evidencia.
* Estrategias.
* Orden.
* Diccionarios.
* Reglas.
* Máscaras.
* Keyspace.
* Duración.
* Recursos.
* Temperatura.
* Condición de detención.

## Estados

```text
CREATED
VALIDATING
QUEUED
RUNNING
PAUSED
RESTORING
RECOVERED
EXHAUSTED
TIME_LIMIT_REACHED
RESOURCE_LIMIT_REACHED
CANCELLED
FAILED
```

## Criterios de aceptación

* Calcular keyspace antes de iniciar.
* Mostrar velocidad.
* Mostrar progreso.
* Mostrar tiempo transcurrido.
* Pausar.
* Reanudar.
* Restaurar tras reinicio.
* Cancelar procesos completos.
* Detenerse al recuperar una clave.
* Proteger el resultado.
* Registrar exactamente qué espacio fue evaluado.

---

# 19. Protección de contraseñas recuperadas

## Requisitos

* No guardar en logs generales.
* No mostrar en notificaciones.
* Cifrar en base de datos.
* Redactar en informes.
* Registrar acceso al secreto.
* Permitir anexo cifrado.
* Permitir eliminación segura.
* No transmitir al frontend sin solicitud explícita.

## Representación

```text
Contraseña recuperada: sí
Valor mostrado: Empr*********!
Longitud: 13
Método: diccionario y regla
Tiempo: 00:03:42
Patrón: organización + año + símbolo
```

---

# 20. Módulo WPA3

## Objetivo

Evaluar configuración y comportamiento de redes WPA3.

## Funciones

* Detectar SAE.
* Detectar Transition Mode.
* Detectar H2E.
* Detectar SAE-PK.
* Comprobar PMF.
* Analizar grupos criptográficos.
* Identificar downgrade de configuración.
* Detectar clientes conectados mediante WPA2.
* Analizar inconsistencias RSN.
* Registrar implementaciones sospechosas.

## Regla fundamental

La plataforma no tratará un handshake WPA3-SAE como un handshake WPA2 recuperable mediante el mismo flujo offline.

## Extensiones de laboratorio

* Fuzzing SAE.
* Mutación de mensajes.
* Alteración de estados.
* Anti-clogging.
* Repetición de commits.
* Omisión de mensajes.
* Orden incorrecto.
* Detección de crashes.

---

# 21. Módulo WPS

## Funciones

* Detectar WPS.
* Detectar método PIN.
* Detectar Push Button.
* Identificar fabricante.
* Identificar UUID.
* Detectar bloqueo.
* Detectar rate limiting.
* Validar Pixie Dust.
* Evaluar PIN predecible.
* Registrar intentos.

## Controles

* Máximo de intentos.
* Tiempo máximo.
* Cooldown.
* Detención ante bloqueo.
* Detención ante pérdida de servicio.
* Ejecución solo sobre BSSID autorizado.

---

# 22. Módulo PMF

## Funciones

* Detectar PMF deshabilitado.
* Detectar PMF opcional.
* Detectar PMF obligatorio.
* Comparar beacon y asociación.
* Identificar clientes sin PMF.
* Validar resiliencia.
* Generar hallazgo.
* Recomendar PMF obligatorio.

## Severidad orientativa

* WPA3 sin PMF obligatorio: alta.
* WPA2 corporativo con PMF deshabilitado: media o alta.
* PMF opcional: media.
* PMF obligatorio: informativo positivo.

---

# 23. Módulo WPA-Enterprise

## Funciones pasivas

* Detectar 802.1X.
* Identificar métodos EAP.
* Analizar certificados.
* Extraer CN.
* Extraer SAN.
* Detectar CA.
* Revisar vencimiento.
* Revisar algoritmo.
* Detectar identidad externa.
* Detectar PEAP.
* Detectar EAP-TTLS.
* Detectar EAP-TLS.

## Funciones activas autorizadas

* Rogue AP de laboratorio.
* Validación de certificados.
* Validación de perfiles.
* Comprobación de autoaceptación.
* Pruebas contra dispositivos controlados.
* Captura protegida de challenge-response.

## Protección

* No almacenar contraseñas en texto plano.
* Cifrar evidencia sensible.
* Limitar pruebas a clientes controlados.
* Registrar dispositivo y operador.
* Separar resultados técnicos y credenciales.

---

# 24. Módulo de aislamiento y segmentación

## Pruebas

* Cliente a cliente.
* Cliente a gateway.
* Invitado a LAN.
* Invitado a servidores.
* Entre VLAN.
* Entre BSSID.
* Entre AP.
* Entre SSID.
* Acceso a panel administrativo.
* ARP.
* DHCP.
* DNS.
* mDNS.
* LLMNR.
* NBNS.
* IPv6 Neighbor Discovery.

## Resultado esperado

```text
Prueba: cliente invitado a servidor interno
Resultado: conexión permitida
Destino: 10.0.40.10:445
Severidad: crítica
Evidencia: captura y registro de conexión
```

---

# 25. Detección de rogue AP

## Indicadores

* BSSID no inventariado.
* Mismo SSID con cifrado diferente.
* Certificado RADIUS diferente.
* PMF degradado.
* Canal anómalo.
* Fabricante incompatible.
* Potencia inusual.
* WPS inesperado.
* AKM diferente.
* Beacon interval diferente.
* RSN Information Element diferente.

## Puntuación

Cada indicador sumará o restará puntos.

```text
Probabilidad rogue AP: 87/100

+35 Certificado desconocido
+20 BSSID no autorizado
+15 PMF degradado
+10 Cifrado diferente
+10 Señal anormal
-03 Fabricante coincidente
```

---

# 26. Sistema persistente de trabajos

## Objetivo

Gestionar correctamente procesos que pueden durar minutos u horas.

## Flujo

```text
JobManager
    ↓
PolicyEngine
    ↓
JobQueue
    ↓
ProcessSupervisor
    ↓
ToolAdapter
    ↓
OutputParser
    ↓
EvidenceStore
    ↓
FindingEngine
```

## Estados

```text
CREATED
VALIDATING_SCOPE
QUEUED
PREPARING
RUNNING
WAITING_FOR_EVIDENCE
PAUSED
CANCELLING
CANCELLED
COMPLETED
FAILED
TIMED_OUT
RESOURCE_LIMITED
```

## Requisitos

* Persistencia.
* Prioridades.
* Workers limitados.
* Heartbeats.
* Timeout.
* Streaming.
* Cancelación.
* Recuperación tras reinicio.
* Grupos de procesos.
* Logs grandes en archivos.
* SHA-256.
* Resultados parciales.
* WebSocket con replay.
* Progreso indeterminado cuando no exista parser.
* Limpieza posterior.

---

# 27. Adaptadores

Cada herramienta externa tendrá un adaptador independiente.

## Interfaz base

```python
class ToolAdapter:
    async def validate_installation(self) -> bool:
        ...

    async def get_version(self) -> str:
        ...

    async def build_command(self, options):
        ...

    async def start(self, context):
        ...

    async def parse_output(self, line: str):
        ...

    async def collect_results(self):
        ...

    async def cleanup(self):
        ...
```

## Adaptadores iniciales

* KismetAdapter.
* AirodumpAdapter.
* HcxdumptoolAdapter.
* HcxPcapngToolAdapter.
* HashcatAdapter.
* TsharkAdapter.
* AircrackAdapter.
* ReaverAdapter.
* BullyAdapter.
* EAPHammerAdapter.
* HostapdAdapter.
* NmapAdapter.

## Regla

La lógica principal nunca deberá depender directamente de la salida textual de una herramienta. Cada adaptador será responsable de normalizar los resultados.

---

# 28. Modelo de datos

## Engagement

* id.
* name.
* client.
* operator.
* status.
* start_date.
* end_date.
* authorization_reference.
* permissions.
* limits.
* notes.

## ScopeTarget

* id.
* engagement_id.
* ssid.
* bssid.
* channel.
* band.
* permission_level.
* notes.

## AccessPoint

* id.
* engagement_id.
* ssid.
* bssid.
* vendor.
* channel.
* frequency.
* signal.
* protocol.
* akm.
* cipher.
* pmf.
* wps.
* first_seen.
* last_seen.

## Station

* id.
* mac.
* randomized.
* vendor.
* associated_bssid.
* signal.
* first_seen.
* last_seen.
* controlled.

## Capture

* id.
* engagement_id.
* path.
* format.
* sha256.
* interface.
* channel.
* tool.
* tool_version.
* started_at.
* finished_at.

## HandshakeArtifact

* id.
* access_point_id.
* station_id.
* capture_id.
* message_pair.
* quality.
* validated.
* hash22000_path.
* created_at.

## CrackingJob

* id.
* artifact_id.
* strategy.
* keyspace.
* progress.
* speed.
* status.
* recovered.
* encrypted_secret.
* restore_path.
* started_at.
* finished_at.

## Finding

* id.
* engagement_id.
* title.
* category.
* severity.
* confidence.
* description.
* impact.
* evidence.
* remediation.
* affected_assets.
* status.

---

# 29. Motor de hallazgos

## Objetivo

Convertir resultados técnicos en hallazgos profesionales.

## Ejemplos

### Contraseña WPA2 recuperable

```yaml
id: WIFI-PSK-001
title: Contraseña WPA2 recuperable
severity: critical
conditions:
  - cracking.result == RECOVERED
```

### WPS PIN habilitado

```yaml
id: WIFI-WPS-001
title: WPS PIN habilitado
severity: high
conditions:
  - network.wps.enabled == true
  - network.wps.pin == true
```

### PMF opcional

```yaml
id: WIFI-PMF-001
title: Protected Management Frames opcional
severity: medium
conditions:
  - network.pmf == optional
```

### WPA3 Transition Mode

```yaml
id: WIFI-WPA3-001
title: WPA3 configurado en modo transición
severity: medium
conditions:
  - network.sae == true
  - network.psk == true
```

## Campos obligatorios

* Título.
* Severidad.
* Confianza.
* Activo.
* Descripción.
* Evidencia.
* Impacto.
* Reproducción.
* Remediación.
* Referencias.
* Fecha.
* Estado.

---

# 30. Gestión de evidencias

## Estructura

```text
engagements/
└── ENG-2026-001/
    ├── authorization/
    ├── captures/
    │   ├── original/
    │   └── normalized/
    ├── handshakes/
    ├── hashes/
    ├── cracking/
    ├── screenshots/
    ├── logs/
    ├── findings/
    ├── exports/
    └── reports/
```

## Metadatos

* SHA-256.
* Fecha.
* Zona horaria.
* Operador.
* Herramienta.
* Versión.
* Interfaz.
* Driver.
* Canal.
* BSSID.
* SSID.
* Acción.
* Trabajo.
* Archivo original.
* Archivo derivado.
* Validación.
* Cadena de custodia.

## Requisitos

* Inmutabilidad lógica.
* No sobrescritura.
* Hash automático.
* Redacción de datos sensibles.
* Cifrado opcional.
* Registro de acceso.
* Exportación controlada.

---

# 31. Informes

## Informe ejecutivo

Incluirá:

* Cliente.
* Alcance.
* Fechas.
* Metodología.
* Nivel de riesgo.
* Cantidad de redes.
* Hallazgos críticos.
* Hallazgos altos.
* Impacto.
* Prioridades.
* Recomendaciones generales.

## Informe técnico

Incluirá:

* Hardware.
* Drivers.
* Herramientas.
* Versiones.
* Redes.
* Clientes.
* Seguridad.
* Handshakes.
* PMKID.
* Planes de cracking.
* Keyspace.
* Tiempo.
* Resultados.
* WPA3.
* WPS.
* PMF.
* Enterprise.
* Segmentación.
* Evidencias.
* Hallazgos.
* Remediaciones.

## Exportaciones

* PDF.
* HTML.
* JSON.
* CSV.
* ZIP de evidencias.
* Anexo cifrado.

---

# 32. Interfaz de usuario

## Páginas principales

### Dashboard

* Interfaces.
* Engagement activo.
* Redes detectadas.
* Objetivos autorizados.
* Handshakes.
* PMKID.
* Trabajos activos.
* GPU.
* Temperatura.
* Hallazgos.

### Engagements

* Crear.
* Editar.
* Activar.
* Pausar.
* Cerrar.
* Archivar.
* Importar alcance.

### Live Scan

* Tabla de AP.
* Tabla de clientes.
* Filtros.
* Mapa de canales.
* Seguridad.
* Señal.
* Estado de alcance.

### Network Detail

* Datos de red.
* Clientes.
* Capturas.
* Handshakes.
* PMKID.
* Hallazgos.
* Acciones permitidas.

### Handshakes

* Estado.
* Calidad.
* Message pair.
* Cliente.
* Conversión.
* Evidencias.

### Cracking Jobs

* Estrategia.
* Keyspace.
* Velocidad.
* Progreso.
* Temperatura.
* Tiempo.
* Estado.
* Pausar.
* Reanudar.
* Cancelar.

### Findings

* Severidad.
* Confianza.
* Evidencia.
* Impacto.
* Remediación.
* Estado.

### Reports

* Plantilla.
* Secciones.
* Vista previa.
* Exportación.
* Anexo.

---

# 33. CLI

```text
aegiswifi interface list
aegiswifi interface inspect wlan1
aegiswifi interface monitor-start wlan1
aegiswifi interface restore wlan1

aegiswifi engagement create
aegiswifi engagement activate ENG-001
aegiswifi scope import authorization.yaml
aegiswifi scope validate

aegiswifi scan start
aegiswifi network list
aegiswifi network inspect <bssid>

aegiswifi handshake capture <target>
aegiswifi handshake validate <capture>
aegiswifi handshake convert <capture>

aegiswifi crack plan <artifact>
aegiswifi crack start <plan>
aegiswifi crack status <job>
aegiswifi crack pause <job>
aegiswifi crack resume <job>
aegiswifi crack cancel <job>

aegiswifi audit wps <target>
aegiswifi audit pmf <target>
aegiswifi audit enterprise <target>
aegiswifi audit isolation <target>

aegiswifi report generate <engagement>
```

---

# 34. Seguridad de la aplicación

## Medidas obligatorias

* API limitada a localhost.
* Autenticación local.
* Protección CSRF.
* Validación estricta de entrada.
* No ejecutar comandos mediante shell.
* Argumentos como listas.
* Lista permitida de binarios.
* Variables de entorno controladas.
* Directorios temporales aislados.
* Permisos mínimos.
* Separación de privilegios.
* Logs sin secretos.
* Cifrado de datos sensibles.
* Auditoría de accesos.
* Protección contra path traversal.
* Protección contra command injection.
* Validación de archivos importados.
* Límites de tamaño.
* Control de procesos hijos.

## Privilegios

Se recomienda separar:

* Servicio web sin privilegios.
* Helper privilegiado mínimo.
* Comunicación local autenticada.
* Políticas específicas para operaciones inalámbricas.
* No ejecutar todo el backend como root.

---

# 35. Instalación

## Requisitos

* Kali Linux actualizado.
* Python 3.13.
* Node.js.
* Adaptador compatible.
* Drivers adecuados.
* Hashcat.
* Herramientas inalámbricas.
* GPU opcional.

## Instalador

El script deberá:

1. Detectar Kali.
2. Comprobar arquitectura.
3. Instalar dependencias.
4. Crear entorno virtual.
5. Instalar backend.
6. Instalar frontend.
7. Compilar frontend.
8. Crear directorios.
9. Crear usuario de servicio.
10. Configurar permisos.
11. Registrar servicio.
12. Ejecutar diagnóstico.

## Desinstalador

Deberá:

* Detener servicios.
* Restaurar interfaces.
* Eliminar binarios.
* Mantener o borrar datos según opción.
* Eliminar configuraciones.
* Limpiar permisos.

---

# 36. Pruebas

## Unitarias

* Parsers.
* Validadores.
* Scope Engine.
* Motor de reglas.
* Modelos.
* Adaptadores.
* Protección de secretos.

## Integración

* Aircrack-ng.
* hcxdumptool.
* hcxtools.
* Hashcat.
* Kismet.
* Tshark.
* Base de datos.
* WebSocket.

## PCAP fixtures

Se incluirán capturas de:

* WPA2 completo.
* WPA2 parcial.
* PMKID válido.
* PMKID inválido.
* Múltiples clientes.
* Replay mismatch.
* WPA3.
* Enterprise.
* WPS.
* PMF.

## Laboratorio

* mac80211_hwsim.
* hostapd WPA2.
* hostapd WPA3.
* FreeRADIUS.
* Clientes Linux.
* Redes de invitados.
* Segmentación.
* Rogue AP controlado.

## Seguridad

* Command injection.
* Path traversal.
* Manipulación de alcance.
* Bypass de permisos.
* Lectura de secretos.
* Procesos huérfanos.
* Archivos maliciosos.
* WebSocket no autorizado.

---

# 37. Fases de desarrollo

## Fase 0 — Preparación

### Tareas

* Crear repositorio.
* Definir licencia.
* Crear README.
* Configurar linters.
* Configurar tests.
* Configurar CI.
* Definir convenciones.
* Crear documentación.
* Definir modelo de amenazas.

### Entregable

Repositorio base ejecutable.

---

## Fase 1 — Núcleo

### Tareas

* FastAPI.
* Configuración.
* SQLite.
* Migraciones.
* Logging.
* API base.
* WebSocket.
* Sistema de jobs.
* Gestión de errores.
* Health checks.

### Criterio de aceptación

La aplicación inicia, persiste trabajos y transmite eventos.

---

## Fase 2 — Engagement y alcance

### Tareas

* Modelo Engagement.
* Modelo ScopeTarget.
* Importación YAML.
* Policy Engine.
* Permisos.
* Límites.
* Auditoría de acciones.

### Criterio de aceptación

No se ejecuta ninguna acción activa sobre objetivos no autorizados.

---

## Fase 3 — Interfaces

### Tareas

* Detección.
* Chipset.
* Driver.
* Capacidades.
* Monitor mode.
* Inyección.
* Restauración.
* Diagnóstico.

### Criterio de aceptación

La interfaz puede prepararse y restaurarse sin intervención manual.

---

## Fase 4 — Descubrimiento

### Tareas

* Integración Kismet.
* Integración Airodump.
* AP.
* Clientes.
* RSN parser.
* WPS.
* PMF.
* WPA3.
* Tiempo real.

### Criterio de aceptación

El panel muestra el entorno inalámbrico y clasifica correctamente cada red.

---

## Fase 5 — Handshake y PMKID

### Tareas

* Captura.
* Parser EAPOL.
* Parser PMKID.
* Validador.
* Calidad.
* Conversión.
* Evidencias.

### Criterio de aceptación

Una captura válida puede convertirse y asociarse correctamente al objetivo.

---

## Fase 6 — Cracking

### Tareas

* Hashcat Adapter.
* Benchmark.
* Diccionarios.
* Reglas.
* Máscaras.
* Híbridos.
* Keyspace.
* Restore.
* Progreso.
* Temperatura.
* Protección de resultado.

### Criterio de aceptación

Un trabajo puede iniciarse, pausarse, restaurarse y finalizar sin perder estado.

---

## Fase 7 — Hallazgos e informes

### Tareas

* Motor de reglas.
* Severidad.
* Remediaciones.
* HTML.
* PDF.
* JSON.
* Anexo cifrado.

### Criterio de aceptación

La aplicación genera un informe profesional respaldado por evidencia.

---

## Fase 8 — WPS y PMF

### Tareas

* Enumeración.
* Bloqueo.
* Rate limiting.
* Pixie Dust.
* Validación PMF.
* Reconexión controlada.

### Criterio de aceptación

Las pruebas respetan límites y se detienen automáticamente.

---

## Fase 9 — Enterprise

### Tareas

* Parser EAP.
* Certificados.
* EAPHammer.
* hostapd-wpe.
* Clientes controlados.
* Evidencia sensible.

### Criterio de aceptación

La plataforma identifica configuraciones inseguras sin exponer credenciales.

---

## Fase 10 — Pruebas avanzadas

### Tareas

* FragAttacks.
* SSID Confusion.
* AirSnitch.
* SAE testing.
* Rogue AP.
* Roaming.
* Wi-Fi 6E/7.

### Criterio de aceptación

Cada módulo avanzado funciona de forma aislada y requiere habilitación explícita.

---

# 38. MVP

El MVP deberá incluir:

* Backend local.
* Frontend.
* SQLite.
* Engagements.
* Alcance.
* Interfaces.
* Monitor mode.
* Restauración.
* Descubrimiento.
* Clasificación WPA/WPA2/WPA3.
* WPS.
* PMF.
* Captura EAPOL.
* Captura PMKID.
* Validación.
* Conversión 22000.
* Hashcat.
* Diccionario.
* Reglas.
* Máscaras.
* Progreso.
* Evidencias.
* Hallazgos.
* Informe HTML.
* Informe PDF.

El MVP no incluirá inicialmente:

* Evil Twin.
* WPA-Enterprise activo.
* FragAttacks.
* SAE fuzzing.
* AirSnitch.
* Sensores remotos.
* Multiusuario.

---

# 39. Definición de terminado

Una funcionalidad se considera terminada cuando:

* Está implementada.
* Tiene tests.
* Tiene manejo de errores.
* Tiene logs estructurados.
* Respeta el Scope Engine.
* Tiene documentación.
* Tiene validación de entrada.
* Tiene limpieza de recursos.
* Tiene criterios de aceptación cumplidos.
* No expone secretos.
* Puede cancelarse.
* Produce resultados normalizados.
* Funciona en Kali Linux.
* No deja interfaces modificadas.

---

# 40. Riesgos técnicos

## Dependencia del hardware

No todos los adaptadores soportan:

* Monitor mode.
* Inyección.
* 5 GHz.
* 6 GHz.
* AP mode.
* WPA3.
* Canales DFS.

### Mitigación

* Matriz de compatibilidad.
* Diagnóstico automático.
* Adaptadores recomendados.
* Pruebas por chipset.

## Salidas inestables

Las herramientas externas pueden cambiar formatos.

### Mitigación

* Adaptadores versionados.
* Parsers con fixtures.
* Validación de versiones.
* Formatos estructurados cuando estén disponibles.

## Privilegios

Algunas funciones requieren root.

### Mitigación

* Helper privilegiado.
* Separación de procesos.
* Políticas mínimas.
* No ejecutar la UI como root.

## Trabajos prolongados

Hashcat puede ejecutar durante horas.

### Mitigación

* Persistencia.
* Restore.
* Heartbeats.
* Límites.
* Pausa.
* Recuperación.

## Evidencia sensible

Las capturas pueden contener información privada.

### Mitigación

* Cifrado.
* Redacción.
* Control de acceso.
* Exportación consciente.
* Política de retención.

---

# 41. Métricas del proyecto

## Técnicas

* Cobertura de tests.
* Errores por módulo.
* Tiempo de recuperación.
* Trabajos restaurados.
* Precisión de clasificación.
* Capturas válidas.
* Falsos positivos.
* Tiempo de generación de reportes.

## Operativas

* Auditorías completadas.
* Redes evaluadas.
* Hallazgos por severidad.
* Tiempo medio por auditoría.
* Porcentaje de tareas automatizadas.
* Fallos de interfaces.
* Trabajos cancelados.

---

# 42. Entregables

## Entregables principales

1. Código fuente.
2. Instalador para Kali Linux.
3. Backend.
4. Frontend.
5. CLI.
6. Base de datos.
7. Sistema de jobs.
8. Adaptadores.
9. Motor de reglas.
10. Plantillas de informes.
11. Laboratorio.
12. Tests.
13. Documentación.
14. Modelo de amenazas.
15. Guía de uso.
16. Guía de desarrollo.
17. Guía de auditoría.
18. Matriz de compatibilidad.

---

# 43. Criterios de éxito

El proyecto será considerado exitoso cuando permita:

* Detectar adaptadores compatibles.
* Preparar interfaces.
* Descubrir redes.
* Identificar WPA2 y WPA3.
* Capturar handshakes válidos.
* Detectar PMKID.
* Convertir evidencia.
* Ejecutar auditorías de contraseña autorizadas.
* Mostrar progreso.
* Restaurar trabajos.
* Proteger contraseñas.
* Generar hallazgos.
* Generar informes.
* Restaurar completamente el sistema.
* Bloquear acciones fuera de alcance.

---

# 44. Posicionamiento del producto

AegisWiFi no deberá presentarse como un programa destinado únicamente a crackear redes.

El posicionamiento correcto será:

> Plataforma profesional de evaluación inalámbrica para detectar configuraciones inseguras, validar la fortaleza de credenciales, comprobar segmentación, identificar puntos de acceso fraudulentos y generar evidencia técnica reproducible.

El cracking será una capacidad central para demostrar el impacto de contraseñas débiles, pero formará parte de un proceso controlado de auditoría.

---

# 45. Próximos pasos inmediatos

1. Crear el repositorio.
2. Definir arquitectura.
3. Crear `AGENTS.md`.
4. Crear modelo de datos.
5. Implementar backend base.
6. Implementar sistema de jobs.
7. Implementar Engagement y Scope Engine.
8. Implementar detección de interfaces.
9. Implementar monitor mode y restauración.
10. Integrar Kismet o Airodump-ng.
11. Crear inventario de AP.
12. Implementar captura y validación EAPOL.
13. Implementar conversión 22000.
14. Integrar Hashcat.
15. Crear panel inicial.
16. Generar primer informe HTML.

---

# 46. Resultado esperado de la primera entrega

La primera entrega funcional deberá permitir:

1. Iniciar AegisWiFi en Kali Linux.
2. Crear un engagement.
3. Importar un alcance autorizado.
4. Seleccionar una interfaz.
5. Activar monitor mode.
6. Escanear redes.
7. Seleccionar una red autorizada.
8. Capturar evidencia WPA2.
9. Validar el handshake.
10. Convertirlo al formato 22000.
11. Crear un plan de auditoría de contraseña.
12. Ejecutarlo mediante Hashcat.
13. Mostrar el progreso.
14. Registrar el resultado.
15. Generar un hallazgo.
16. Exportar un informe.
17. Restaurar la interfaz.

Esta entrega constituirá el núcleo sobre el que se agregarán posteriormente WPS, WPA3 avanzado, Enterprise, aislamiento, FragAttacks y demás módulos especializados.
