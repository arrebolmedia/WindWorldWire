# Article Rewriter System

## Objetivos: Convertir clusters (o picks de topics) en artículos listos para publicar

El sistema de reescritura de artículos convierte clusters de noticias en artículos periodísticos optimizados para SEO, listos para publicación, con validación anti-alucinación y múltiples formatos de salida.

## 🎯 Características Principales

### ✅ Anti-Alucinación
- **Validación estricta contra fuentes**: Verifica que todo el contenido esté respaldado por las fuentes originales
- **Detección de números inventados**: Identifica cifras, fechas y datos específicos no presentes en fuentes
- **Validación de citas**: Asegura que todas las citas textuales existan en el material original
- **Puntuación de credibilidad**: Sistema de scoring que evalúa la veracidad del contenido

### 🔍 Optimización SEO
- **Títulos optimizados**: 30-70 caracteres con palabras clave relevantes
- **Meta descriptions**: 120-160 caracteres con call-to-action
- **Slugs SEO-friendly**: URLs limpias y descriptivas
- **Estructura de headings**: Jerarquía H1-H6 optimizada
- **JSON-LD**: Structured data para mejor indexación
- **Keywords relevantes**: Extracción y optimización automática

### 📝 Múltiples Formatos
- **JSON estructurado**: Para integración con CMS
- **HTML completo**: Con metadatos y SEO markup
- **WordPress**: Formato Gutenberg compatible
- **AMP**: Versión optimizada para móviles
- **Preview**: Vista previa para editores

### 🏗️ Arquitectura Modular

```
newsbot/rewriter/
├── models.py              # Modelos Pydantic con validación
├── llm_provider.py        # Abstracción de LLMs con fallbacks
├── validators.py          # Sistema de validación anti-alucinación
├── seo_rewriter.py        # Lógica principal de reescritura
├── template_renderer.py   # Generación de HTML seguro
├── app.py                 # API FastAPI
└── __init__.py           # Exportaciones principales
```

## 🚀 Instalación y Configuración

### Requisitos
```bash
pip install -r requirements-rewriter.txt
```

### Configuración Básica
```python
from newsbot.rewriter import SEOArticleRewriter, rewrite_cluster_quick

# Uso rápido
cluster_data = {
    "topic": "Energía Renovable en España",
    "summary": "Crecimiento del sector renovable",
    "sources": [
        {
            "url": "https://example.com/noticia",
            "title": "España instala 1,200 MW de solar",
            "summary": "Récord de instalación solar",
            "content": "España ha instalado 1,200 MW..."
        }
    ]
}

article = await rewrite_cluster_quick(cluster_data, "es")
```

## 📊 API Endpoints

### Servidor de Desarrollo
```bash
cd newsbot
python -m newsbot.rewriter.app
```

El servidor estará disponible en `http://localhost:8003`

### Endpoints Principales

#### `GET /health`
Estado del sistema y componentes
```json
{
  "status": "healthy",
  "components": {
    "rewriter": "healthy",
    "llm_provider": "DummyLLMProvider"
  }
}
```

#### `GET /rewrite/mock-data`
Datos de prueba para testing
```json
{
  "mock_cluster": {
    "topic": "Energía Renovable en España",
    "sources": [...]
  }
}
```

#### `POST /rewrite`
Conversión principal de cluster a artículo
```json
{
  "cluster": {
    "topic": "Tu tema",
    "sources": [{"url": "...", "title": "...", "content": "..."}]
  },
  "language": "es",
  "quality_mode": "balanced",
  "output_format": "json"
}
```

**Respuesta:**
```json
{
  "success": true,
  "article": {...},
  "validation_results": {...},
  "quality_score": 85.2,
  "processing_time": 2.3
}
```

#### `POST /rewrite/preview`
Vista previa HTML del artículo generado

## 🧪 Modos de Calidad

### `quick` (Rápido)
- Generación básica sin validación extensiva
- Tiempo: ~1-2 segundos
- Uso: Previews y borradores

### `balanced` (Balanceado) 
- Validación estándar con 2 iteraciones
- Tiempo: ~3-5 segundos  
- Uso: Artículos de producción normales

### `comprehensive` (Comprensivo)
- Validación estricta con 3 iteraciones
- Puntuación mínima: 85/100
- Tiempo: ~5-10 segundos
- Uso: Artículos de alta importancia

## 🔬 Sistema de Validación

### Validación Anti-Alucinación
```python
from newsbot.rewriter.validators import AntiHallucinationValidator

validator = AntiHallucinationValidator(strict_mode=True)
result = validator.validate_article_against_sources(article, source_data)

print(f"Válido: {result.is_valid}")
print(f"Puntuación: {result.score}/100") 
print(f"Errores: {result.errors}")
```

### Validación SEO
```python
from newsbot.rewriter.validators import SEOComplianceValidator

seo_validator = SEOComplianceValidator()
seo_result = seo_validator.validate_seo_compliance(article)

# Verifica título, meta description, estructura, keywords
```

### Validación de Calidad de Contenido
```python
from newsbot.rewriter.validators import ContentQualityValidator

quality_validator = ContentQualityValidator()
quality_result = quality_validator.validate_content_quality(article)

# Verifica legibilidad, coherencia, completitud
```

## 🎨 Generación de Templates

### HTML Completo
```python
from newsbot.rewriter.template_renderer import render_article_html

html = render_article_html(article, template_type="default")
# Incluye: SEO metadata, structured data, CSS optimizado
```

### WordPress
```python
wp_content = render_article_html(article, template_type="wordpress")
# Formato: Bloques Gutenberg compatibles
```

### AMP
```python
amp_html = render_article_html(article, template_type="amp")
# Optimizado: Carga rápida en móviles
```

## 🔧 Configuración Avanzada

### LLM Provider Personalizado
```python
from newsbot.rewriter.llm_provider import LLMProvider

class CustomLLMProvider(LLMProvider):
    async def generate_article(self, cluster_data, language, prompt=None):
        # Tu implementación personalizada
        return generated_content

# Configurar factory
LLMProviderFactory.register_provider("custom", CustomLLMProvider)
```

### Validadores Personalizados
```python
from newsbot.rewriter.validators import ValidationResult

def custom_validator(article, source_data):
    result = ValidationResult(True)
    
    # Tu lógica de validación
    if some_condition:
        result.add_error("Error personalizado")
    
    return result
```

## 🧪 Testing

### Tests de Integración
```bash
cd newsbot
python test_rewriter_validation.py
```

### Tests Completos
```bash
pytest tests/test_rewriter_integration.py -v
```

### Test de Performance
```python
import time
start_time = time.time()
article = await rewrite_cluster_quick(large_cluster_data, "es")
processing_time = time.time() - start_time
assert processing_time < 10.0  # Debe completarse en <10 segundos
```

## 📈 Métricas de Calidad

### Puntuación General (0-100)
- **90-100**: Excelente - Listo para publicación inmediata
- **75-89**: Muy bueno - Revisión menor recomendada  
- **60-74**: Aceptable - Requiere revisión
- **40-59**: Deficiente - Necesita regeneración
- **0-39**: Inaceptable - Datos insuficientes

### Componentes de Puntuación
- **Anti-alucinación (40%)**: Sin información inventada
- **SEO (35%)**: Optimización técnica
- **Calidad (25%)**: Legibilidad y coherencia

## 🔍 Troubleshooting

### Error: "No LLM provider available"
```python
# Usar provider dummy para desarrollo
from newsbot.rewriter.llm_provider import DummyLLMProvider
provider = DummyLLMProvider()
```

### Error: "Validation failed"
```python
# Revisar fuentes y contenido
validation_results = validate_complete_article(article, source_data)
for category, result in validation_results.items():
    print(f"{category}: {result.errors}")
```

### Error: "Template rendering failed"
```python
# Verificar datos del artículo
try:
    article.dict()  # Debe serializar sin errores
except Exception as e:
    print(f"Error en modelo: {e}")
```

## 🚀 Roadmap

### Próximas Características
- [ ] Integración con LLMs reales (OpenAI, Claude, Llama)
- [ ] Soporte para más idiomas (inglés, francés, italiano)
- [ ] Optimización para diferentes tipos de contenido
- [ ] API de métricas y analytics
- [ ] Plugin para CMS populares
- [ ] Generación automática de imágenes
- [ ] Integración con sistemas de fact-checking

### Mejoras Técnicas
- [ ] Caché de respuestas LLM
- [ ] Rate limiting y throttling
- [ ] Monitoreo con Prometheus
- [ ] Despliegue con Docker
- [ ] CI/CD automatizado
- [ ] Base de datos para métricas

## 📞 Soporte

Para problemas, reportes de bugs o solicitudes de características:

1. **Documentación**: Revisar este README y comentarios en código
2. **Testing**: Ejecutar `python test_rewriter_validation.py`
3. **Logs**: Revisar logs en `/logs/rewriter.log`
4. **Debug**: Usar modo verbose en validadores

## 📄 Licencia

Copyright © 2024 Wind World Wire. Todos los derechos reservados.

---

**🎯 Objetivo cumplido**: Sistema completo para convertir clusters en artículos listos para publicar con validación anti-alucinación, optimización SEO y múltiples formatos de salida.