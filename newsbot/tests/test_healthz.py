"""Health check tests for all NewsBot services."""
import pytest
from fastapi.testclient import TestClient


def test_ingestor_healthz():
    """Test ingestor service health check."""
    from newsbot.ingestor.app import app
    
    client = TestClient(app)
    response = client.get("/healthz")
    
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "ingestor"


def test_trender_healthz():
    """Test trender service health check."""
    from newsbot.trender.app import app
    
    client = TestClient(app)
    response = client.get("/healthz")
    
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "trender"


def test_rewriter_healthz():
    """Test rewriter service health check."""
    from newsbot.rewriter.app import app
    
    client = TestClient(app)
    response = client.get("/healthz")
    
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "rewriter"


def test_mediaer_healthz():
    """Test mediaer service health check."""
    from newsbot.mediaer.app import app
    
    client = TestClient(app)
    response = client.get("/healthz")
    
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "mediaer"


def test_publisher_healthz():
    """Test publisher service health check."""
    from newsbot.publisher.app import app
    
    client = TestClient(app)
    response = client.get("/healthz")
    
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "publisher"


def test_watchdog_healthz():
    """Test watchdog service health check."""
    from newsbot.watchdog.app import app
    
    client = TestClient(app)
    response = client.get("/healthz")
    
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "watchdog"


def test_all_services_root_endpoint():
    """Test root endpoint for all services."""
    services = [
        ("ingestor", "newsbot.ingestor.app"),
        ("trender", "newsbot.trender.app"),
        ("rewriter", "newsbot.rewriter.app"),
        ("mediaer", "newsbot.mediaer.app"),
        ("publisher", "newsbot.publisher.app"),
        ("watchdog", "newsbot.watchdog.app"),
    ]
    
    for service_name, module_path in services:
        # Import the app dynamically
        module = __import__(module_path, fromlist=["app"])
        app = getattr(module, "app")
        
        client = TestClient(app)
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data
    from newsbot.rewriter.app import app
    
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "rewriter"


def test_mediaer_health():
    """Test mediaer health check."""
    from newsbot.mediaer.app import app
    
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "mediaer"


def test_publisher_health():
    """Test publisher health check."""
    from newsbot.publisher.app import app
    
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "publisher"


def test_watchdog_health():
    """Test watchdog health check."""
    from newsbot.watchdog.app import app
    
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "watchdog"


@pytest.mark.parametrize("service_name", [
    "ingestor", "trender", "rewriter", 
    "mediaer", "publisher", "watchdog"
])
def test_service_root_endpoint(service_name):
    """Test root endpoint for all services."""
    module = __import__(f"newsbot.{service_name}.app", fromlist=["app"])
    app = module.app
    
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "NewsBot" in response.json()["message"]
    assert response.json()["version"] == "0.1.0"