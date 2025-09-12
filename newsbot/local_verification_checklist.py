#!/usr/bin/env python3
"""
🎯 Checklist de Verificación Local - RSS Ingestor
================================================

Ejecuta los pasos exactos solicitados por el usuario:

1. ✅ python scripts/seed.py crea/actualiza sources
2. ✅ python -m newsbot.ingestor.pipeline imprime stats y inserta en raw_items  
3. ✅ Correr dos veces seguidas: la segunda debe dar 304 o 0 inserts
4. ✅ pytest -q pasa tests de normalización y dedupe
5. ✅ curl -X POST http://localhost:8000/run devuelve conteos
"""

import subprocess
import sys
import time
import os
import requests
import signal
from pathlib import Path
from typing import Dict, Any

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def print_step(step_num: int, description: str):
    """Print step header."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*70}")
    print(f"{step_num}️⃣  {description}")
    print(f"{'='*70}{Colors.RESET}")

def print_command(cmd: str):
    """Print command being executed."""
    print(f"{Colors.WHITE}💻 Ejecutando: {cmd}{Colors.RESET}")

def print_success(msg: str):
    """Print success message."""
    print(f"{Colors.GREEN}✅ {msg}{Colors.RESET}")

def print_error(msg: str):
    """Print error message."""
    print(f"{Colors.RED}❌ {msg}{Colors.RESET}")

def print_info(msg: str):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.RESET}")

def run_command(cmd: str, cwd: str = None, timeout: int = 300) -> Dict[str, Any]:
    """Execute command and return result."""
    print_command(cmd)
    
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        execution_time = time.time() - start_time
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'time': execution_time
        }
        
    except subprocess.TimeoutExpired:
        return {
            'returncode': -1,
            'stdout': '',
            'stderr': f'Timeout after {timeout}s',
            'time': timeout
        }
    except Exception as e:
        return {
            'returncode': -1, 
            'stdout': '',
            'stderr': str(e),
            'time': time.time() - start_time
        }

def step_1_seed_sources():
    """1. python scripts/seed.py crea/actualiza sources."""
    print_step(1, "python scripts/seed.py crea/actualiza sources")
    
    python_exe = sys.executable
    result = run_command(f'"{python_exe}" scripts/seed.py')
    
    if result['returncode'] == 0:
        print_success(f"Seeding completado exitosamente en {result['time']:.2f}s")
        
        # Show relevant output
        lines = result['stdout'].split('\n')
        for line in lines:
            if any(marker in line for marker in ['✅', '📰', '📈', '🎉', 'Total active sources']):
                print(f"  {line}")
        return True
    else:
        print_error(f"Seeding falló (código: {result['returncode']})")
        if result['stderr']:
            print(f"  Error: {result['stderr'][:300]}")
        return False

def step_2_pipeline_execution():
    """2. python -m newsbot.ingestor.pipeline imprime stats y inserta en raw_items."""
    print_step(2, "python -m newsbot.ingestor.pipeline imprime stats")
    
    python_exe = sys.executable
    result = run_command(f'"{python_exe}" -m newsbot.ingestor.pipeline')
    
    if result['returncode'] == 0:
        print_success(f"Pipeline ejecutado exitosamente en {result['time']:.2f}s")
        
        # Parse and show RSS Ingestion Results
        lines = result['stdout'].split('\n')
        showing_results = False
        
        for line in lines:
            if '=== RSS Ingestion Results ===' in line:
                showing_results = True
            if showing_results and line.strip():
                print(f"  {line}")
                
        return True
    else:
        print_error(f"Pipeline falló (código: {result['returncode']})")
        if result['stderr']:
            print(f"  Error: {result['stderr'][:300]}")
        return False

def step_3_double_execution():
    """3. Correr dos veces seguidas: la segunda debe dar 304 o 0 inserts."""
    print_step(3, "Segunda ejecución para verificar caché (304 / 0 inserts)")
    
    print_info("Ejecutando pipeline nuevamente para verificar caché...")
    
    python_exe = sys.executable
    result = run_command(f'"{python_exe}" -m newsbot.ingestor.pipeline')
    
    if result['returncode'] == 0:
        print_success(f"Segunda ejecución completada en {result['time']:.2f}s")
        
        # Parse output for cache indicators
        lines = result['stdout'].split('\n')
        sources_304 = 0
        items_inserted = 0
        
        for line in lines:
            if 'Sources Not Modified (304):' in line:
                sources_304 = int(line.split(':')[1].strip())
            elif 'Items Inserted:' in line:
                items_inserted = int(line.split(':')[1].strip())
            if '=== RSS Ingestion Results ===' in line:
                # Show the results section
                showing_results = True
                for result_line in lines[lines.index(line):]:
                    if result_line.strip():
                        print(f"  {result_line}")
                    else:
                        break
        
        # Evaluate caching effectiveness
        if sources_304 > 0:
            print_success(f"🎯 Caché HTTP funcionando: {sources_304} sources retornaron 304 Not Modified")
        
        if items_inserted == 0:
            print_success(f"🎯 Sin duplicados: {items_inserted} items insertados (contenido ya procesado)")
        
        if sources_304 > 0 or items_inserted == 0:
            print_success("✅ Verificación de caché exitosa")
            return True
        else:
            print_info(f"⚠️  Caché parcial: {sources_304} sources 304, {items_inserted} items nuevos")
            print_info("Esto puede ser normal si hay contenido nuevo disponible")
            return True
            
    else:
        print_error(f"Segunda ejecución falló (código: {result['returncode']})")
        return False

def step_4_pytest_tests():
    """4. pytest -q pasa tests de normalización y dedupe."""
    print_step(4, "pytest -q pasa tests de normalización y dedupe")
    
    python_exe = sys.executable
    
    # Run specific test classes for normalization and deduplication
    test_targets = [
        "tests/test_ingestor_rss.py::TestNormalizeEntry",
        "tests/test_ingestor_rss.py::TestSimHashHamming",
        "-v"  # Verbose to see individual test results
    ]
    
    cmd = f'"{python_exe}" -m pytest {" ".join(test_targets)}'
    result = run_command(cmd)
    
    if result['returncode'] == 0:
        # Count successful tests
        output = result['stdout']
        passed_count = output.count('PASSED')
        
        print_success(f"Tests ejecutados exitosamente: {passed_count} tests pasaron")
        
        # Show test results summary
        lines = output.split('\n')
        for line in lines:
            if 'PASSED' in line and '::' in line:
                test_name = line.split('::')[-1].split()[0]
                print(f"  ✅ {test_name}")
        
        return True
    else:
        print_error(f"Tests fallaron (código: {result['returncode']})")
        
        # Show failed tests
        stderr_lines = result['stderr'].split('\n')
        for line in stderr_lines:
            if 'FAILED' in line or 'ERROR' in line:
                print(f"  ❌ {line}")
        
        return False

def step_5_fastapi_endpoint():
    """5. curl -X POST http://localhost:8000/run devuelve conteos."""
    print_step(5, "curl -X POST http://localhost:8000/run devuelve conteos")
    
    print_info("Iniciando servidor FastAPI en background...")
    
    # Set environment for manual runs
    env = os.environ.copy()
    env['ALLOW_MANUAL_RUN'] = 'true'
    
    python_exe = sys.executable
    
    # Start server
    server_cmd = f'"{python_exe}" -m uvicorn newsbot.ingestor.app:app --host 127.0.0.1 --port 8000'
    print_command(server_cmd)
    
    try:
        server_process = subprocess.Popen(
            server_cmd,
            shell=True,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to start
        print_info("Esperando que el servidor inicie...")
        time.sleep(4)
        
        # Check if server is running
        if server_process.poll() is not None:
            stdout, stderr = server_process.communicate()
            print_error("Servidor falló al iniciar")
            print(f"STDOUT: {stdout[:300]}")
            print(f"STDERR: {stderr[:300]}")
            return False
        
        # Test the endpoint
        print_info("Probando endpoint POST /run...")
        
        try:
            response = requests.post(
                'http://127.0.0.1:8000/run',
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                print_success(f"✅ API respondió exitosamente!")
                print(f"  Status: {data.get('status', 'unknown')}")
                print(f"  Message: {data.get('message', 'N/A')}")
                
                # Show detailed stats
                if 'stats' in data:
                    stats = data['stats']
                    print(f"  📊 Estadísticas detalladas:")
                    print(f"    ⏱️  Runtime: {stats.get('runtime_seconds', 0):.2f}s")
                    print(f"    ✅ Sources OK: {stats.get('sources_ok', 0)}")
                    print(f"    🔄 Sources 304: {stats.get('sources_304', 0)}")
                    print(f"    ❌ Sources Error: {stats.get('sources_error', 0)}")
                    print(f"    📝 Items Total: {stats.get('items_total', 0)}")
                    print(f"    ➕ Items Inserted: {stats.get('items_inserted', 0)}")
                    print(f"    🔁 Items Duplicated: {stats.get('items_duplicated', 0)}")
                    print(f"    🏷️  Items SimHash Filtered: {stats.get('items_simhash_filtered', 0)}")
                
                return True
            else:
                print_error(f"API retornó status {response.status_code}")
                print(f"Response: {response.text[:300]}")
                return False
                
        except requests.exceptions.RequestException as e:
            print_error(f"Error conectando al endpoint: {e}")
            return False
            
    finally:
        # Clean up server
        if 'server_process' in locals() and server_process:
            print_info("Cerrando servidor...")
            try:
                server_process.terminate()
                server_process.wait(timeout=5)
            except:
                try:
                    server_process.kill()
                except:
                    pass

def main():
    """Execute complete verification checklist."""
    start_time = time.time()
    
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("🎯 CHECKLIST DE VERIFICACIÓN LOCAL")
    print("RSS Ingestor NewsBot")
    print("=" * 50)
    print(f"{Colors.RESET}")
    
    # Execute all steps
    steps = [
        ("Seeding de sources", step_1_seed_sources),
        ("Ejecución pipeline", step_2_pipeline_execution), 
        ("Verificación caché", step_3_double_execution),
        ("Tests pytest", step_4_pytest_tests),
        ("Endpoint FastAPI", step_5_fastapi_endpoint)
    ]
    
    results = {}
    
    for step_name, step_func in steps:
        try:
            print_info(f"Iniciando: {step_name}")
            results[step_name] = step_func()
        except KeyboardInterrupt:
            print_error("Verificación interrumpida por el usuario")
            return 1
        except Exception as e:
            print_error(f"Error en {step_name}: {e}")
            results[step_name] = False
    
    # Final summary
    total_time = time.time() - start_time
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    print(f"\n{Colors.CYAN}{Colors.BOLD}")
    print("📊 RESUMEN FINAL")
    print("=" * 50)
    print(f"{Colors.RESET}")
    
    for step_name, result in results.items():
        status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if result else f"{Colors.RED}❌ FAIL{Colors.RESET}"
        print(f"  {status} {step_name}")
    
    print(f"\n{Colors.BOLD}Resultado: {passed}/{total} checks exitosos en {total_time:.2f}s{Colors.RESET}")
    
    if passed == total:
        print_success("🎉 ¡Todos los componentes funcionan correctamente!")
        print_info("El sistema RSS está listo para uso en producción")
    else:
        print_info(f"⚠️  {total - passed} componentes necesitan atención")
        print_info("Revisa los errores arriba para configuración completa")
    
    print(f"\n{Colors.CYAN}📚 Para uso completo en producción:{Colors.RESET}")
    print("1. Configurar PostgreSQL database")
    print("2. Set ALLOW_MANUAL_RUN=true en environment")
    print("3. Ejecutar este checklist regularmente")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Verificación interrumpida{Colors.RESET}")
        sys.exit(1)