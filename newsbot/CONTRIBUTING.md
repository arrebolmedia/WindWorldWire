# Contribuir a NewsBot

¡Gracias por tu interés en contribuir a NewsBot! Este documento proporciona pautas y información sobre cómo contribuir efectivamente al proyecto.

## 📋 Tabla de Contenidos

- [Código de Conducta](#código-de-conducta)
- [Cómo Contribuir](#cómo-contribuir)
- [Estándares de Desarrollo](#estándares-de-desarrollo)
- [Proceso de Pull Request](#proceso-de-pull-request)
- [Reportar Bugs](#reportar-bugs)
- [Solicitar Features](#solicitar-features)
- [Configuración de Desarrollo](#configuración-de-desarrollo)

## 🤝 Código de Conducta

Este proyecto adhiere al código de conducta del [Contributor Covenant](https://www.contributor-covenant.org/). Al participar, se espera que mantengas este código. Por favor reporta comportamientos inaceptables a tech@windworldwire.com.

## 🚀 Cómo Contribuir

### Tipos de Contribuciones

Damos la bienvenida a varios tipos de contribuciones:

- **🐛 Fixes de bugs**: Correcciones de errores reportados
- **✨ Nuevas características**: Implementación de funcionalidades nuevas
- **📚 Documentación**: Mejoras en documentación y ejemplos
- **🧪 Testing**: Adición o mejora de pruebas
- **🔧 Refactoring**: Mejoras en la calidad del código
- **🌐 Traducciones**: Localizaciones y traducciones

### Flujo de Trabajo

1. **Fork** el repositorio
2. **Crea** una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. **Desarrolla** tu contribución siguiendo los estándares
4. **Escribe** o actualiza tests
5. **Ejecuta** las pruebas y verifica que pasen
6. **Commit** tus cambios con mensajes descriptivos
7. **Push** a tu fork (`git push origin feature/nueva-funcionalidad`)
8. **Abre** un Pull Request

## 🛠️ Estándares de Desarrollo

### Estilo de Código

- **Python**: Seguimos PEP 8 con algunas modificaciones definidas en `ruff.toml`
- **Líneas**: Máximo 88 caracteres por línea
- **Imports**: Organizados alfabéticamente usando `isort`
- **Formato**: Aplicamos `black` para formateo automático
- **Type hints**: Obligatorios para todas las funciones públicas

### Convenciones de Nomenclatura

```python
# Clases: PascalCase
class ArticleProcessor:
    pass

# Funciones y variables: snake_case
def process_article():
    article_count = 0

# Constantes: UPPER_SNAKE_CASE
MAX_ARTICLES_PER_BATCH = 100

# Archivos: snake_case
# article_processor.py
```

### Estructura de Commits

Usamos [Conventional Commits](https://www.conventionalcommits.org/) en español:

```
tipo(alcance): descripción breve

Descripción más detallada si es necesaria.

- Cambio específico 1
- Cambio específico 2

Closes #123
```

**Tipos de commit:**
- `feat`: Nueva funcionalidad
- `fix`: Corrección de bug
- `docs`: Cambios en documentación
- `style`: Cambios de formato (no afectan la lógica)
- `refactor`: Refactoring de código
- `test`: Adición o modificación de pruebas
- `chore`: Cambios en build, herramientas, etc.

**Ejemplos:**
```
feat(ingestor): agregar soporte para fuentes RSS con autenticación

fix(database): corregir conexión con PostgreSQL en ambiente de pruebas

docs(readme): actualizar instrucciones de instalación

test(core): agregar pruebas unitarias para modelos de dominio
```

### Testing

#### Cobertura Mínima
- **Unit tests**: 90%+ de cobertura
- **Integration tests**: Flujos críticos cubiertos
- **E2E tests**: Casos de uso principales

#### Estructura de Tests
```
tests/
├── unit/                   # Pruebas unitarias
│   ├── test_models.py
│   ├── test_services.py
│   └── ...
├── integration/            # Pruebas de integración
│   ├── test_database.py
│   ├── test_redis.py
│   └── ...
├── e2e/                   # Pruebas end-to-end
│   ├── test_article_workflow.py
│   └── ...
└── conftest.py            # Configuración compartida
```

#### Escribir Tests

```python
import pytest
from newsbot.core.models import Article

class TestArticle:
    """Tests para el modelo Article."""
    
    def test_create_article_with_valid_data(self):
        """Debería crear un artículo con datos válidos."""
        article = Article(
            title="Test Article",
            content="Test content",
            url="https://example.com"
        )
        
        assert article.title == "Test Article"
        assert article.status == ArticleStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_save_article_to_database(self, db_session):
        """Debería guardar el artículo en la base de datos."""
        # Test implementation
        pass
```

### Documentación

#### Docstrings
Usamos el formato Google para docstrings:

```python
def process_article(article_id: str, options: dict = None) -> ProcessResult:
    """Procesa un artículo aplicando las reglas de negocio.
    
    Args:
        article_id: ID único del artículo a procesar
        options: Opciones adicionales de procesamiento
        
    Returns:
        ProcessResult: Resultado del procesamiento con métricas
        
    Raises:
        ArticleNotFoundError: Si el artículo no existe
        ProcessingError: Si falla el procesamiento
        
    Example:
        >>> result = process_article("123", {"rewrite": True})
        >>> print(result.status)
        'completed'
    """
```

#### Comentarios
- **Qué hacer**: Comentarios en español explicando la lógica de negocio
- **Qué evitar**: Comentarios obvios que solo repiten el código

```python
# ✅ Bueno
# Aplicamos descuento del 15% para clientes premium mexicanos
if customer.country == "MX" and customer.tier == "premium":
    discount = 0.15

# ❌ Malo
# Incrementa el contador en 1
counter += 1
```

## 🔄 Proceso de Pull Request

### Antes de Enviar

1. **Sincroniza** tu fork con el repositorio principal
2. **Ejecuta** todas las verificaciones:
   ```bash
   # Linting y formato
   uv run ruff check newsbot/ tests/
   uv run ruff format newsbot/ tests/
   
   # Type checking
   uv run mypy newsbot/
   
   # Tests
   uv run pytest --cov=newsbot
   ```
3. **Actualiza** documentación si es necesario
4. **Verifica** que todos los tests pasen

### Template de Pull Request

```markdown
## 📝 Descripción

Breve descripción de los cambios realizados.

## 🎯 Tipo de Cambio

- [ ] Bug fix (cambio que corrige un issue)
- [ ] Nueva feature (cambio que agrega funcionalidad)
- [ ] Breaking change (fix o feature que cambiaría funcionalidad existente)
- [ ] Documentación

## 🧪 Testing

- [ ] Tests unitarios agregados/actualizados
- [ ] Tests de integración agregados/actualizados
- [ ] Todas las pruebas pasan localmente

## 📋 Checklist

- [ ] Mi código sigue los estándares del proyecto
- [ ] He revisado mi propio código
- [ ] He comentado áreas complejas del código
- [ ] He actualizado la documentación correspondiente
- [ ] Mis cambios no generan nuevas advertencias
- [ ] He agregado tests que prueban mi fix/feature
- [ ] Tests nuevos y existentes pasan localmente

## 🔗 Issues Relacionados

Fixes #(issue_number)

## 📷 Screenshots (si aplica)

Incluir capturas de pantalla para cambios en UI.
```

### Revisión de Código

Los PRs serán revisados considerando:

- **Funcionalidad**: ¿El código hace lo que se supone que debe hacer?
- **Calidad**: ¿Es legible, mantenible y eficiente?
- **Testing**: ¿Está bien probado?
- **Documentación**: ¿Está bien documentado?
- **Estándares**: ¿Sigue las convenciones del proyecto?

## 🐛 Reportar Bugs

### Antes de Reportar

1. **Busca** en issues existentes
2. **Verifica** que sea realmente un bug
3. **Prueba** con la versión más reciente

### Template de Bug Report

```markdown
## 🐛 Descripción del Bug

Descripción clara y concisa del problema.

## 🔄 Pasos para Reproducir

1. Vaya a '...'
2. Haga clic en '...'
3. Desplácese hacia abajo hasta '...'
4. Vea el error

## 🎯 Comportamiento Esperado

Descripción clara de lo que esperaba que pasara.

## 📱 Entorno

- OS: [ej. macOS, Linux, Windows]
- Python: [ej. 3.11.5]
- NewsBot: [ej. 0.1.0]
- Docker: [ej. 24.0.6]

## 📎 Información Adicional

Logs, capturas de pantalla, etc.
```

## ✨ Solicitar Features

### Template de Feature Request

```markdown
## 🚀 Feature Request

### 📋 Resumen
Descripción clara y concisa de la feature solicitada.

### 🎯 Problema que Resuelve
¿Qué problema resuelve esta feature?

### 💡 Solución Propuesta
Descripción detallada de cómo funcionaría.

### 🔄 Alternativas Consideradas
Otras soluciones que consideraste.

### 📊 Impacto
- Performance
- Compatibilidad
- Mantenimiento
```

## ⚙️ Configuración de Desarrollo

### Requisitos del Sistema

- Python 3.11+
- Docker 20.10+
- Docker Compose 2.0+
- Git 2.30+

### Configuración Inicial

```bash
# 1. Fork y clonar
git clone https://github.com/tu-usuario/newsbot.git
cd newsbot

# 2. Configurar upstream
git remote add upstream https://github.com/windworldwire/newsbot.git

# 3. Instalar dependencias
uv sync --all-extras

# 4. Configurar pre-commit hooks
uv run pre-commit install

# 5. Copiar configuración de ejemplo
cp .env.example .env

# 6. Levantar servicios de desarrollo
docker-compose up -d postgres redis

# 7. Ejecutar migraciones
uv run python scripts/seed.py

# 8. Verificar instalación
uv run pytest tests/
```

### Variables de Entorno para Desarrollo

```env
# Desarrollo
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Base de datos local
DATABASE_URL=postgresql+asyncpg://newsbot:newsbot@localhost:5432/newsbot_dev
DATABASE_URL_SYNC=postgresql://newsbot:newsbot@localhost:5432/newsbot_dev

# Redis local
REDIS_URL=redis://localhost:6379/0

# APIs de desarrollo (opcionales)
OPENAI_API_KEY=sk-...
NEWS_API_KEY=...
```

### Herramientas de Desarrollo

#### VS Code
Configuración recomendada en `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "./.venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "files.associations": {
        "*.yaml": "yaml"
    }
}
```

#### Extensions Recomendadas
- Python
- Ruff
- YAML
- Docker
- GitLens

### Debugging

#### Logs de Desarrollo
```bash
# Ver logs de todos los servicios
docker-compose logs -f

# Ver logs de un servicio específico
docker-compose logs -f ingestor

# Ejecutar servicio en modo debug
DEBUG=true uv run python -m newsbot.services.ingestor.main
```

#### Debugging con IDE
```python
# Para debug con breakpoints
import debugpy
debugpy.listen(("0.0.0.0", 5678))
debugpy.wait_for_client()
```

## 📞 Contacto

- **Issues**: [GitHub Issues](https://github.com/windworldwire/newsbot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/windworldwire/newsbot/discussions)
- **Email**: tech@windworldwire.com
- **Slack**: #newsbot-dev (para colaboradores)

## 🙏 Reconocimientos

¡Gracias a todos los contribuidores que hacen posible este proyecto!

<!-- TODO: Agregar all-contributors cuando tengamos colaboradores -->

---

**¿Tienes dudas?** No dudes en preguntar en GitHub Discussions o abrir un issue. ¡Estamos aquí para ayudar! 🚀