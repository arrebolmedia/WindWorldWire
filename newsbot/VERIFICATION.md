# NewsBot Quick Verification Checklist

Follow these steps to verify your NewsBot setup is working correctly:

## ✅ 1. Start Infrastructure Services

```bash
# Start all infrastructure services
docker compose -f infra/docker-compose.yml up -d
```

**Expected result:**
- ✅ postgres container running on port 5432
- ✅ redis container running on port 6379  
- ✅ opensearch container running on port 9200
- ✅ temporal container running on port 7233
- ✅ temporal-ui accessible at http://localhost:8080

**Verify:**
```bash
docker compose -f infra/docker-compose.yml ps
```

## ✅ 2. Create Database Tables and Seed Data

```bash
# Run database seeding script
python scripts/seed.py
```

**Expected result:**
```
🌱 Starting NewsBot database seeding...
📊 Creating database tables...
✅ Tables created successfully
🔌 Connected to database

📰 Seeding sources...
Added source: Reuters World
Added source: AP Top
Added source: El País Internacional

🏷️  Seeding topics...
Added topic: Taiwán y seguridad regional

==================================================
🎉 DATABASE SEEDING COMPLETE!
==================================================
📰 Sources added: 3
🏷️  Topics added: 1
```

## ✅ 3. Test Publisher Service Health Check

```bash
# Start publisher service with hot reload
uvicorn newsbot.publisher.app:app --reload
```

**Expected result:**
- ✅ Service starts on http://localhost:8000
- ✅ Health check responds: `curl http://localhost:8000/healthz`
  ```json
  {"ok": true, "service": "publisher"}
  ```
- ✅ Root endpoint responds: `curl http://localhost:8000/`
  ```json
  {"service": "publisher", "version": "0.1.0"}
  ```

## ✅ 4. Run All Tests

```bash
# Run test suite quietly
pytest -q
```

**Expected result:**
```
........                                                         [100%]
8 passed in 0.15s
```

**All health check tests should pass:**
- ✅ test_ingestor_healthz
- ✅ test_trender_healthz  
- ✅ test_rewriter_healthz
- ✅ test_mediaer_healthz
- ✅ test_publisher_healthz
- ✅ test_watchdog_healthz
- ✅ test_all_services_root_endpoint

## ✅ 5. Environment Configuration

```bash
# Copy environment template and fill in values
cp .env.example .env
# Edit .env with your specific values
```

**Required .env variables:**
```bash
TZ=America/Mexico_City
DB_URL=postgresql+asyncpg://news:news@postgres:5432/news
REDIS_URL=redis://redis:6379/0
OPENSEARCH_URL=http://opensearch:9200
WP_BASE_URL=https://your-wordpress.com
WP_USER=bot
WP_APP_PASSWORD=xxxx
FB_PAGE_ID=1234567890
FB_PAGE_TOKEN=EAAG...
LOG_LEVEL=INFO
```

## 🚀 Bonus Verification Steps

### Check All Services with Docker Compose
```bash
# Build and start all services
docker compose -f infra/docker-compose.yml up --build

# Verify all containers are healthy
docker compose -f infra/docker-compose.yml ps
```

### Run VS Code Tasks
- **Ctrl+Shift+P** → "Tasks: Run Task"
- ✅ `compose:up` - Start infrastructure
- ✅ `tests` - Run tests
- ✅ `lint` - Check code quality
- ✅ `compose:down` - Clean shutdown

### Test Individual Service Health Checks
```bash
# Test each service (if running via Docker)
curl http://localhost:8001/healthz  # ingestor
curl http://localhost:8002/healthz  # trender
curl http://localhost:8003/healthz  # rewriter
curl http://localhost:8004/healthz  # mediaer
curl http://localhost:8005/healthz  # publisher
curl http://localhost:8006/healthz  # watchdog
```

## 🎯 Success Criteria

✅ **Infrastructure**: All Docker services running and accessible  
✅ **Database**: Tables created and seeded with sources/topics  
✅ **Services**: Publisher health check returns `{"ok": true, "service": "publisher"}`  
✅ **Tests**: All pytest health checks pass  
✅ **Configuration**: .env file properly configured  

## 🛠️ Troubleshooting

**If something fails:**

1. **Check Docker logs**: `docker compose -f infra/docker-compose.yml logs [service]`
2. **Verify environment**: Ensure .env file has correct database URLs
3. **Check ports**: Make sure no conflicts on 5432, 6379, 9200, 7233, 8080
4. **Dependencies**: Run `pip install -e .` to install project dependencies
5. **Database connection**: Verify postgres is running and accessible

## 📚 Quick Reference

- **Project structure**: `newsbot/` contains all services and core modules
- **Configuration**: `config/` contains YAML files for sources, topics, policies
- **Tests**: `tests/` contains health check and integration tests
- **Scripts**: `scripts/` contains database seeding and utility scripts
- **Infrastructure**: `infra/` contains Docker Compose and deployment files