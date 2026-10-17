# Hoja de Trabajo 6 - Evals con Promptfoo

Sistema de asistencia conversacional para **Parachute S.A.** con integración a la base de conocimientos de FAQs (HDT4), verificación meteorológica en tiempo real mediante la API de Open-Meteo y agendamiento seguro de citas para paracaidismo, implementado bajo tres patrones de orquestación multiagente: Centralizada, Jerárquica y Descentralizada. Se seleccionó la aquitectura **Centralizada** para realizar la HDT6.

---

## 1. Descripción del Problema y Requerimientos

Parachute S.A. ha expandido las capacidades de su agente conversacional con nuevos requerimientos de negocio:

- **Base de Conocimientos FAQs**: Respuestas precisas sobre políticas, equipo, seguridad y servicios generales utilizando la base de conocimiento vectorial de HDT4.
- **Consulta Meteorológica en Tiempo Real (Open-Meteo)**:
  - **Coordenadas del lugar de aterrizaje**: `14.013722, -90.771611`.
  - **Ventana de predicción**: Hasta **16 días** a partir de la fecha actual. Si el usuario solicita agendar después de 16 días, el agente debe corregir amablemente e indicar la limitación técnica del pronóstico.
  - **Variables evaluadas**: Velocidad de viento en superficie (`wind_speed_10m`), ráfagas de viento (`wind_gust_10m`), temperatura (`temperature_2m`), precipitación (`precipitation`) y cobertura de nubes/visibilidad (`cloud_cover`).
- **Criterios de Seguridad y Reglas de Vuelo**:
  - **Velocidad de viento en superficie**:
    - *Ideal*: `< 20 km/h`
    - *Marginal (Solo tándem experimentado)*: `20 – 28 km/h`
    - *NO SEGURO / PROHIBIDO*: `> 28 km/h` (condiciones críticas de control)
  - **Ráfagas de viento**:
    - *NO SEGURO / PROHIBIDO*: `> 35 km/h`
  - **Precipitación**:
    - *NO SEGURO / PROHIBIDO*: `> 0.0 mm` (la lluvia daña el equipo y lastima la piel)
  - **Cobertura de nubes / Visibilidad**:
    - *Ideal*: `< 30%` (visibilidad clara)
    - *Marginal*: `30% – 75%` (nubes dispersas)
    - *NO SEGURO / PROHIBIDO*: `> 75%` (un techo de nubes bajo impide las reglas de vuelo visual VFR)
- **Agendamiento Seguro de Citas**: Solo se confirman citas si el clima es `IDEAL` o `MARGINAL`. Si el clima es `INSEGURO` o la fecha excede los 16 días, la cita no se calendariza.
- **Capa de Abstracción Compartida**: Toda la lógica determinista (Open-Meteo, cálculo de umbrales, búsqueda de FAQs y persistencia de citas) reside en `shared/parachute.py`, garantizando que ninguna arquitectura diverja en las reglas de negocio y facilitando escalar requerimientos futuros.

---

## 2. Arquitecturas de Orquestación Implementadas

El sistema resuelve el mismo problema mediante tres arquitecturas independientes utilizando el OpenAI / Agents SDK:

### A. Arquitectura Centralizada (`centralizada.py`)
- **Patrón**: Supervisor / Workers coordinados mediante `as_tool()`.
- **Estructura**: Un agente supervisor central (`SupervisorAgent`) expone a los agentes especializados (`WeatherWorker`, `FAQWorker`, `CalendarWorker`) como herramientas ejecutables.
- **Flujo**: El supervisor recibe todas las entradas del usuario, decide dinámicamente a qué worker invocar como herramienta, recopila la información y sintetiza la respuesta final.
- **Diagrama**: `diagramas/centralizada.mmd`.

### B. Arquitectura Jerárquica (`jerarquica.py`)
- **Patrón**: Árbol de delegación multinivel (Root Manager $\rightarrow$ Specialized Managers $\rightarrow$ Workers).
- **Estructura**: Un gestor raíz (`OperationsManager`) coordina a dos gerentes de área (`InformationManager` para FAQs/clima y `BookingManager` para citas). Cada gerente orquesta a sus propios workers especializados.
- **Flujo**: Permite separar responsabilidades de alto nivel (consultas informativas vs. operaciones transaccionales) antes de llegar a la ejecución de herramientas.
- **Diagrama**: `diagramas/jerarquica.mmd`.

### C. Arquitectura Descentralizada (`descentralizada.py`)
- **Patrón**: Red de pares (Peer-to-Peer) con delegación mediante `handoff()`.
- **Estructura**: Agentes pares (`IntakeAgent`, `WeatherAgent`, `FAQAgent`, `CalendarAgent`) que se transfieren el control directo de la conversación usando un esquema tipado `HandoffPayload` compatible con Groq.
- **Flujo**: No existe un orquestador central permanente. Cualquier agente especialista puede transferir la conversación a otro colega según el giro de la conversación.
- **Diagrama**: `diagramas/descentralizada.mmd`.

---

## 3. Requisitos y Configuración del Entorno

### Requisitos
- Python 3.10 o superior.
- Base de datos PostgreSQL con `pgvector` de la HDT4 (opcional; si no está activa, el módulo utiliza fallback determinista en memoria sobre el corpus oficial).
- Clave de API de Groq (o OpenAI).

### Configuración Inicial

1. **Clonar el repositorio y ubicarse en la raíz del proyecto**:
   ```bash
   cd hdt6-ai
   ```

2. **Crear y configurar el `.env` principal**:
   ```bash
   cp .env.example .env
   ```

   Completar como mínimo las variables del proveedor de modelos:
   ```dotenv
   GROQ_API_KEY=gsk_...
   GROQ_MODEL=openai/gpt-oss-20b
   GROQ_BASE_URL=https://api.groq.com/openai/v1
   ```

   El mismo archivo contiene las variables de PostgreSQL utilizadas por la HDT4:
   `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` y
   `POSTGRES_HOST`. Estas variables también deben estar disponibles en
   `hdt4/.env`, porque el cargador de FAQs y la integración RAG leen la configuración
   desde ese archivo.

   La forma más sencilla de mantener ambos archivos sincronizados es:
   ```bash
   cp .env hdt4/.env
   ```

3. **Activar el entorno virtual e instalar dependencias**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Cargar las variables de entorno en la sesión actual**:
   ```bash
   set -a
   source .env
   set +a
   ```

5. **Levantar PostgreSQL + pgvector con Docker Compose**:
   ```bash
   docker compose -f hdt4/docker-compose.yml up -d
   ```

6. **Cargar el corpus oficial de FAQs**:
   ```bash
   python hdt4/src/load_corpus.py \
     --corpus data/Corpus_FAQs_Parachute_SA_2026.txt
   ```

   La salida esperada termina con un mensaje similar a:
   ```text
   Carga completada: 120 FAQs insertadas/actualizadas. Total actual en la tabla: 120.
   ```
---

## 4. Ejecución de las Arquitecturas

Cada programa soporta dos modalidades: **consulta única vía argumentos** o **sesión de chat interactiva**:

### Ejecución de Arquitectura Centralizada
```bash
# Modo consulta única
python centralizada.py "¿Qué requisitos físicos necesito para saltar?"
python centralizada.py "Quiero calendarizar una cita el 2026-10-01"

# Modo chat interactivo
python centralizada.py
```

### Ejecución de Arquitectura Jerárquica
```bash
# Modo consulta única
python jerarquica.py "¿Cuál es la política de cancelación?"
python jerarquica.py "Quiero calendarizar una cita el 2026-10-01"

# Modo chat interactivo
python jerarquica.py
```

### Ejecución de Arquitectura Descentralizada
```bash
# Modo consulta única
python descentralizada.py "Hola, quisiera información de precios y agendar para este sábado"
python descentralizada.py "Quiero calendarizar una cita el 2026-10-01"

# Modo chat interactivo
python descentralizada.py
```

---

## 5. Pruebas y Validación

### Pruebas Unitarias Automatizadas
El proyecto incluye pruebas deterministas con `unittest` que evalúan todos los umbrales meteorológicos, límites de fechas de 16 días, formatos inválidos y reglas de reserva sin depender de llamadas de red:

```bash
python -m unittest discover -s tests -v
```

### Suite Exhaustiva de Casos y Consulta en Vivo (`probar_todos_casos.py`)
Permite verificar de forma rápida todos los casos borde y probar la integración real con Open-Meteo:

```bash
# Validación determinista de reglas meteorológicas y validación de fechas
python probar_todos_casos.py

# Verificación de pronósticos reales en vivo con Open-Meteo para los 17 días disponibles
python probar_todos_casos.py --live
```

### Evals de la arquitectura centralizada (Promptfoo)

La suite de `evals/` ejecuta el supervisor centralizado mediante
`evals/provider.py`. Las citas usan fixtures meteorológicos y almacenamiento
temporal; las FAQs siguen usando la integración HDT4 configurada localmente.

```bash
# La ruta local evita problemas de permisos en ~/.promptfoo en entornos aislados.
PROMPTFOO_CONFIG_DIR="$PWD/.promptfoo" npx promptfoo eval \
  -c evals/promptfooconfig.yaml
```

La configuración ejecuta un caso a la vez y limita cada llamada del proveedor a
60 segundos; una dependencia remota bloqueada queda reportada como error en vez
de dejar la corrida abierta. Los asserts son deterministas (salida, traza de
herramientas y persistencia), por lo que no añaden llamadas de un modelo juez.

---

## 6. Estructura del Repositorio

```text
orchestration/
├── centralizada.py            # Implementación con supervisor y as_tool()
├── jerarquica.py              # Implementación con Root/Managers y as_tool()
├── descentralizada.py         # Implementación peer-to-peer con handoff()
├── probar_todos_casos.py      # Script de verificación de reglas y clima en vivo
├── shared/
│   ├── __init__.py
│   └── parachute.py           # Abstracción compartida: Open-Meteo, reglas climáticas, FAQs y citas
├── diagramas/
│   ├── centralizada.mmd       # Diagrama de flujo de arquitectura centralizada
│   ├── jerarquica.mmd         # Diagrama de flujo de arquitectura jerárquica
│   └── descentralizada.mmd    # Diagrama de flujo de arquitectura descentralizada
├── tests/
│   └── test_parachute.py      # Pruebas unitarias de umbrales, guardas y fechas
├── data/
│   ├── Corpus_FAQs_Parachute_SA_2026.txt # Dump de 120 preguntas frecuentes oficiales
│   └── citas.json             # Persistencia JSON de citas agendadas
├── respuestas_hdt5.md         # Documento con el análisis de las preguntas planteadas
├── respuestas_hdt5.pdf        # Documento PDF formal de entrega
├── requirements.txt           # Librerías de Python requeridas
├── .env.example               # Plantilla de variables de entorno
└── README.md                  # Documentación principal de la Hoja de Trabajo 5
```

---

## 7. Preguntas de Análisis y Respuestas

El análisis detallado y las respuestas a las preguntas de diseño planteadas por Parachute S.A. se encuentran desarrolladas en **`respuestas_hdt5.md`** y compiladas en **`respuestas_hdt5.pdf`**:

1. **¿Qué arquitectura/arquitecturas resuelven mejor este problema? ¿Por qué?**
   - Comparación entre Centralizada, Jerárquica y Descentralizada en cuanto a simplicidad, latencia, consumo de tokens, determinismo de seguridad y mantenibilidad.
2. **¿Considera que es necesario utilizar un sistema multiagente en este caso? ¿Por qué?**
   - Evaluación crítica entre la complejidad operativa de un sistema multiagente frente a un agente único con function calling y herramientas deterministas bien encapsuladas.
