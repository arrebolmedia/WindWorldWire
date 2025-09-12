# NewsBot - WindWorldWire News Processing System

![CI/CD](https://github.com/windworldwire/newsbot/workflows/CI/CD%20Pipeline/badge.svg)
![Security](https://github.com/windworldwire/newsbot/workflows/Security%20Audit/badge.svg)
[![codecov](https://codecov.io/gh/windworldwire/newsbot/branch/main/graph/badge.svg)](https://codecov.io/gh/windworldwire/newsbot)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-00a393.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

NewsBot es un sistema automatizado de procesamiento de noticias diseñado para WindWorldWire, especializado en contenido de negocios mexicanos. El sistema ingiere, procesa, analiza y publica noticias financieras y empresariales de múltiples fuentes en español.

## 🏗️ Arquitectura

NewsBot está construido como un monorepo de microservicios usando FastAPI, con los siguientes componentes:

### Servicios

- **🔄 Ingestor**: Ingesta noticias de diversas fuentes (RSS, APIs, scraping)
- **📈 Trender**: Analiza tendencias y scoring de engagement
- **✍️ Rewriter**: Reescribe y localiza contenido usando IA
- **🎨 Mediaer**: Procesa y optimiza contenido multimedia
- **📢 Publisher**: Publica contenido en múltiples plataformas
- **🔍 Watchdog**: Monitoreo y alertas del sistema

### Infraestructura

- **PostgreSQL**: Base de datos principal
- **Redis**: Cache y cola de mensajes
- **Temporal**: Orquestación de workflows
- **OpenSearch**: Búsqueda y analytics
- **Docker**: Containerización

## 🚀 Inicio Rápido

### Prerrequisitos

- Python 3.11+
- Docker y Docker Compose
- uv (gestor de dependencias)

### Instalación

1. **Clonar el repositorio**
   ```bash
   git clone https://github.com/windworldwire/newsbot.git
   cd newsbot
   ```

2. **Configurar entorno virtual**
   ```bash
   # Instalar uv si no lo tienes
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Crear entorno e instalar dependencias
   uv sync --all-extras
   ```

3. **Configurar variables de entorno**
   ```bash
   cp .env.example .env
   # Editar .env con tus configuraciones
   ```

4. **Levantar infraestructura**
   ```bash
   docker-compose up -d postgres redis temporal opensearch
   ```

5. **Inicializar base de datos**
   ```bash
   uv run python scripts/seed.py
   ```

6. **Ejecutar servicios**
   ```bash
   # Ejecutar todos los servicios
   docker-compose up -d
   
   # O ejecutar individualmente para desarrollo
   uv run python -m newsbot.services.ingestor.main
   ```

### Verificar Instalación

```bash
# Verificar health checks de todos los servicios
curl http://localhost:8001/healthz  # Ingestor
curl http://localhost:8002/healthz  # Trender
curl http://localhost:8003/healthz  # Rewriter
curl http://localhost:8004/healthz  # Mediaer
curl http://localhost:8005/healthz  # Publisher
curl http://localhost:8006/healthz  # Watchdog
```

## 🛠️ Desarrollo

### Estructura del Proyecto

```
newsbot/
├── newsbot/                    # Código fuente principal
│   ├── core/                   # Paquete compartido
│   │   ├── database.py         # Configuración DB
│   │   ├── settings.py         # Configuración app
│   │   ├── logging.py          # Sistema de logs
│   │   └── models.py           # Modelos de dominio
│   └── services/               # Microservicios
│       ├── ingestor/           # Servicio ingesta
│       ├── trender/            # Servicio análisis
│       ├── rewriter/           # Servicio reescritura
│       ├── mediaer/            # Servicio multimedia
│       ├── publisher/          # Servicio publicación
│       └── watchdog/           # Servicio monitoreo
├── config/                     # Archivos de configuración
│   ├── sources.yaml            # Fuentes de noticias
│   ├── topics.yaml             # Categorías y temas
│   └── policies.yaml           # Políticas de contenido
├── scripts/                    # Scripts de utilidad
├── tests/                      # Pruebas
├── docker-compose.yml          # Orquestación Docker
└── pyproject.toml             # Configuración Python
```

### Comandos de Desarrollo

```bash
# Linting y formato
uv run ruff check newsbot/
uv run ruff format newsbot/

# Type checking
uv run mypy newsbot/

# Ejecutar tests
uv run pytest

# Tests con cobertura
uv run pytest --cov=newsbot --cov-report=html

# Ejecutar servicio específico
uv run python -m newsbot.services.ingestor.main
```

### Base de Datos

```bash
# Crear migración
uv run alembic revision --autogenerate -m "descripción"

# Ejecutar migraciones
uv run alembic upgrade head

# Seed datos de ejemplo
uv run python scripts/seed.py
```

## 📊 Monitoreo

### Dashboards Disponibles

- **Temporal UI**: http://localhost:8080 - Workflows y tareas
- **OpenSearch Dashboards**: http://localhost:5601 - Analytics y búsqueda
- **Health Checks**: http://localhost:800[1-6]/healthz - Estado servicios

### Métricas

Cada servicio expone métricas de Prometheus en `/metrics`:
- Requests por segundo
- Latencia de respuesta
- Errores y excepciones
- Uso de recursos

## 🔧 Configuración

### Fuentes de Noticias

Configurar en `config/sources.yaml`:

```yaml
sources:
  - name: "El Economista México"
    url: "https://www.eleconomista.com.mx"
    rss_url: "https://www.eleconomista.com.mx/rss/mercados"
    source_type: "rss"
    language: "es"
    priority: 1
```

### Temas y Categorías

Configurar en `config/topics.yaml`:

```yaml
topics:
  - name: "Economía Nacional"
    slug: "economia-nacional"
    keywords: ["economía mexicana", "PIB", "inflación"]
```

### Políticas de Contenido

Configurar en `config/policies.yaml`:

```yaml
content_policies:
  editorial:
    tone: "profesional_objetivo"
    target_audience: "profesionales_negocios_mexico"
```

## 🌍 Internacionalización

El sistema está optimizado para contenido en español mexicano:
- Timezone: `America/Mexico_City`
- Moneda: Peso mexicano (MXN)
- Formato de fechas: dd/mm/yyyy
- Contexto local: Negocios y finanzas de México

## 🔐 Seguridad

- Autenticación JWT para APIs
- Rate limiting por IP
- Validación de contenido
- Escaneo de vulnerabilidades automatizado
- Logs de auditoría

## 📈 Escalabilidad

- Servicios containerizados independientes
- Cola de mensajes asíncrona con Redis
- Base de datos optimizada con índices
- Cache de múltiples niveles
- Load balancing con Docker Swarm/Kubernetes

## 🚢 Despliegue

### Desarrollo
```bash
docker-compose up -d
```

### Producción
```bash
# TODO: Implementar configuración de producción
# - Kubernetes manifests
# - Helm charts
# - Monitoring stack (Prometheus, Grafana)
# - Backup automatizado
```

## 🤝 Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para detalles sobre:
- Estándares de código
- Proceso de pull requests
- Convenciones de commits
- Testing guidelines

## 📝 Changelog

Ver [CHANGELOG.md](CHANGELOG.md) para historial de cambios.

## 📄 Licencia

Este proyecto está licenciado bajo la Licencia MIT - ver [LICENSE](LICENSE) para detalles.

## 👥 Equipo

- **WindWorldWire Tech Team** - *Desarrollo inicial* - [WindWorldWire](https://github.com/windworldwire)

## 🆘 Soporte

- **Issues**: [GitHub Issues](https://github.com/windworldwire/newsbot/issues)
- **Documentación**: [Docs](https://windworldwire.github.io/newsbot)
- **Email**: tech@windworldwire.com

## 🎯 Roadmap

### v0.2.0 (Q1 2025)
- [ ] Integración con APIs de OpenAI/GPT
- [ ] Dashboard web de administración
- [ ] Notificaciones push
- [ ] Métricas avanzadas de engagement

### v0.3.0 (Q2 2025)
- [ ] Machine Learning para clasificación automática
- [ ] Análisis de sentimiento en tiempo real
- [ ] Integración con redes sociales
- [ ] API pública para terceros

### v1.0.0 (Q3 2025)
- [ ] Producto completo y estable
- [ ] Documentación completa
- [ ] Pruebas de carga y performance
- [ ] Certificaciones de seguridad