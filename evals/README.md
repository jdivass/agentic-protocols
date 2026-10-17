# Evidencia de ejecución de herramientas

`evals/provider.py` crea un `ToolCallTrace` nuevo para cada caso de Promptfoo y
lo activa durante toda la ejecución de `run_agent`. La respuesta final continúa
siendo texto en `output`; la evidencia se devuelve en:

```json
{
  "metadata": {
    "tool_calls": [
      {
        "order": 1,
        "name": "consultar_faq",
        "arguments": {"input": "..."},
        "result": "...",
        "error": null,
        "origin": "agent:SupervisorCentral"
      }
    ]
  }
}
```

Se registran las llamadas observables realmente ejecutadas:

- Delegaciones del supervisor a workers (`consultar_faq`, `consultar_clima` y
  `calendarizar_cita`), mediante los hooks del Agents SDK.
- Herramientas locales de los workers, mediante los mismos hooks.
- Búsqueda efectiva de HDT4 (`search_knowledge_base`), en
  `hdt4/src/tools.py`.
- Llamadas directas de los guards, con origen `guard:calendar` o
  `guard:domain`.

El orden se asigna al momento de iniciar cada llamada. Si una excepción impide
que el SDK emita el callback de finalización, la llamada queda registrada con
`result: null` y el error capturado por `run_agent`.

No se infieren llamadas a partir del texto de la respuesta. Tampoco se registran
como herramientas del agente las llamadas HTTP internas de Open-Meteo, las
consultas SQL/embeddings internas de PostgreSQL ni las solicitudes HTTP al
proveedor LLM; la herramienta que las encapsula sí queda registrada cuando fue
ejecutada.

El registro se crea dentro de `call_api`, por lo que cada caso empieza con una
lista vacía y su primer evento tiene `order: 1`.

## Dependencias aisladas por caso

El proveedor acepta variables opcionales en cada caso de Promptfoo:

- `fixed_today`: fecha `YYYY-MM-DD` que usa la validación real de fechas.
- `weather_fixture`: objeto JSON con `temperature_c`, `precipitation_mm`,
  `cloud_cover_pct`, `visibility_m`, `wind_speed_kmh` y `wind_gust_kmh`.
- `weather_sequence`: lista JSON de fixtures consumidos en orden por cada
  consulta meteorológica. Esto permite simular un cambio entre la consulta de
  clima y la reserva.
- `initial_appointments`: lista JSON con las citas iniciales del caso.

Las reglas de `validate_date`, `evaluate_weather` y `schedule_tool` permanecen
activas. Cuando se proporciona un fixture, únicamente se sustituye la fuente de
datos de `fetch_weather`; no se sustituye el LLM ni las herramientas.

Cada caso escribe las citas en un archivo temporal y devuelve el estado en
`metadata.appointments`:

```json
{
  "initial": [],
  "final": [],
  "created": []
}
```

El archivo temporal, la ruta `APPOINTMENTS_PATH`, la fecha fija y los fixtures
se restauran al terminar el caso, incluso si ocurre un error. Los evals nunca
escriben en `data/citas.json`.

## Organización de los casos P2 y P3

Los casos están separados por funcionalidad:

- `cases/faq.yaml` corresponde a P2 y contiene el caso mínimo de FAQ.
- `cases/appointments.yaml` corresponde a P3 y contiene el caso mínimo de
  calendarización.

Estos archivos son esqueletos ejecutables, no los datasets completos de P2 y
P3. Cada responsable puede agregar casos al archivo que le corresponde sin
mezclar las dos funcionalidades.

### Contrato de entrada

Cada caso envía `question` como prompt al agente. Puede incluir estos valores:

| Variable | Contrato |
| --- | --- |
| `reference` | Referencia factual independiente de la respuesta del agente. La usa el juez de factuality. |
| `fixed_today` | Fecha `YYYY-MM-DD` para validar fechas de citas. |
| `weather_fixture` | Objeto JSON con el clima simulado para una consulta. |
| `weather_sequence` | Lista JSON de climas consumidos en orden; sirve para simular cambios entre consultas. |
| `initial_appointments` | Lista JSON con las citas existentes al iniciar el caso. |
| `required_tools`, `forbidden_tools` | Listas JSON de llamadas que deben existir o no existir. |
| `expected_sequence`, `sequence_mode` | Secuencia esperada de nombres de herramientas y modo (`subsequence` o `exact`). |
| `expected_created_appointments` | Cantidad esperada de citas nuevas persistidas. |

Ejemplo mínimo de P2:

```yaml
- vars:
    question: "¿Cuál es el peso máximo permitido para saltar?"
    reference: "El peso máximo permitido para saltar es de 100 kg."
  assert:
    - type: contains
      value: "100 kg"
```

Ejemplo mínimo de P3:

```yaml
- vars:
    question: "Quiero calendarizar una cita el 2026-10-01"
    fixed_today: "2026-09-30"
    weather_fixture: '{"temperature_c":25,"precipitation_mm":0,"cloud_cover_pct":10,"visibility_m":10000,"wind_speed_kmh":10,"wind_gust_kmh":20}'
    initial_appointments: '[]'
```

Los fixtures solo sustituyen las dependencias aislables de fecha, clima y
persistencia temporal. El LLM, las herramientas y las reglas de negocio reales
continúan ejecutándose.

### Contrato de salida y metadata

El proveedor devuelve la respuesta textual en `output`. La evidencia verificable
se encuentra en `metadata`:

```json
{
  "tool_calls": [
    {"order": 1, "name": "consultar_faq", "arguments": {}, "result": "...", "error": null, "origin": "agent:SupervisorCentral"}
  ],
  "appointments": {
    "initial": [],
    "final": [],
    "created": []
  }
}
```

Una frase como “cita agendada” no prueba por sí sola que se ejecutó una
herramienta ni que se persistió una cita. Las assertions reutilizables exigen la
evidencia correspondiente en `metadata.tool_calls` y
`metadata.appointments.created`.

## Factuality y latencia compartidas

`promptfooconfig.yaml` aplica a ambos archivos un `defaultTest` con:

- factuality contra `{{reference}}`, que cada caso debe definir de forma
  independiente y que no se genera a partir de la salida del agente;
- el juez explícito `groq:openai/gpt-oss-20b`;
- una assertion de latencia con umbral inicial de `30000` ms.

Ese umbral es provisional para desarrollo y medición inicial; no representa un
requisito acordado por Parachute S.A. La caché debe desactivarse al medir
latencia:

```bash
source ../ai-function-calls/.venv/bin/activate
set -a; source .env; set +a
npx --no-install promptfoo eval -c evals/promptfooconfig.yaml --no-cache
```

Para ejecutar solo el conjunto inicial de P2 o P3 se puede filtrar por su
descripción:

```bash
npx --no-install promptfoo eval -c evals/promptfooconfig.yaml --no-cache --filter-pattern "P2"
npx --no-install promptfoo eval -c evals/promptfooconfig.yaml --no-cache --filter-pattern "P3"
```
