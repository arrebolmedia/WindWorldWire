#!/usr/bin/env python3
"""
Demo script para mostrar el uso de las funciones de scoring de clusters.

Este script demuestra:
1. Cálculo de scores individuales (trend, diversity, freshness)
2. Score total ponderado
3. Ranking de clusters
4. Persistencia de métricas históricas
5. Integración con base de datos
"""

import asyncio
from datetime import datetime, timezone, timedelta
from newsbot.trender.score import (
    trend_spike_score,
    domain_diversity_score,
    freshness_score,
    total_score,
    persist_cluster_scores,
    rank_clusters,
    score_and_rank_clusters,
    HistoricalMetricsCache,
    update_cluster_scores_in_db
)

def create_sample_clusters():
    """Crea clusters de ejemplo para la demostración."""
    now = datetime.now(timezone.utc)
    
    clusters = [
        {
            'id': 1,
            'status': 'open',
            'items_count': 8,
            'domains': {'eleconomista.com.mx': 3, 'reforma.com': 2, 'milenio.com': 3},
            'items': [
                {'published_at': now - timedelta(minutes=30)},
                {'published_at': now - timedelta(hours=1)},
                {'published_at': now - timedelta(hours=2)},
                {'published_at': now - timedelta(hours=3)},
            ]
        },
        {
            'id': 2,
            'status': 'open',
            'items_count': 15,
            'domains': {'forbes.com.mx': 10, 'expansion.mx': 5},  # Menos diverso
            'items': [
                {'published_at': now - timedelta(hours=6)},
                {'published_at': now - timedelta(hours=8)},
            ]
        },
        {
            'id': 3,
            'status': 'closed',  # Este no aparecerá en ranking
            'items_count': 5,
            'domains': {'universal.com.mx': 2, 'jornada.com.mx': 2, 'excelsior.com.mx': 1},
            'items': [
                {'published_at': now - timedelta(minutes=15)},
            ]
        },
        {
            'id': 4,
            'status': 'open',
            'items_count': 12,
            'domains': {'elfinanciero.com.mx': 4, 'eluniversal.com.mx': 4, 'milenio.com': 4},
            'items': [
                {'published_at': now - timedelta(minutes=45)},
                {'published_at': now - timedelta(hours=1.5)},
                {'published_at': now - timedelta(hours=4)},
            ]
        }
    ]
    
    return clusters

def create_sample_historic_data():
    """Crea datos históricos de ejemplo."""
    return {
        1: [3, 4, 5, 4, 3, 5, 6],  # Media ≈ 4.3, actual = 8 (spike fuerte)
        2: [12, 13, 14, 15, 14, 13, 14],  # Media ≈ 13.6, actual = 15 (spike leve)
        3: [2, 3, 2, 3, 2, 3, 2],  # Media ≈ 2.4, actual = 5 (spike moderado)
        4: [10, 11, 12, 11, 10, 11, 12],  # Media ≈ 11, actual = 12 (spike leve)
    }

def demo_individual_scores():
    """Demuestra el cálculo de scores individuales."""
    print("=" * 60)
    print("DEMO: Cálculo de Scores Individuales")
    print("=" * 60)
    
    clusters = create_sample_clusters()
    historic_data = create_sample_historic_data()
    now = datetime.now(timezone.utc)
    
    for cluster in clusters:
        cluster_id = cluster['id']
        print(f"\n📊 Cluster {cluster_id} (status: {cluster['status']}):")
        print(f"   Items: {cluster['items_count']}")
        print(f"   Dominios: {cluster['domains']}")
        
        # Trend spike score
        historic_counts = historic_data.get(cluster_id)
        trend = trend_spike_score(cluster, historic_counts)
        print(f"   🚀 Trend Score: {trend:.3f}")
        if historic_counts:
            avg_historic = sum(historic_counts) / len(historic_counts)
            print(f"      (Histórico promedio: {avg_historic:.1f}, actual: {cluster['items_count']})")
        
        # Domain diversity score
        diversity = domain_diversity_score(cluster)
        print(f"   🌐 Diversity Score: {diversity:.3f}")
        
        # Freshness score
        freshness = freshness_score(cluster, now, tau_hours=3.0)
        print(f"   ⏰ Freshness Score: {freshness:.3f}")
        
        # Total score
        total = total_score(trend, diversity, freshness)
        print(f"   🎯 Total Score: {total:.3f}")
        print(f"      (0.45×{trend:.2f} + 0.35×{diversity:.2f} + 0.20×{freshness:.2f})")

def demo_ranking():
    """Demuestra el ranking de clusters."""
    print("\n" + "=" * 60)
    print("DEMO: Ranking de Clusters")
    print("=" * 60)
    
    clusters = create_sample_clusters()
    historic_data = create_sample_historic_data()
    now = datetime.now(timezone.utc)
    
    # Aplicar scoring y ranking
    ranked = score_and_rank_clusters(
        clusters, 
        historic_counts_map=historic_data,
        now=now,
        tau_hours=3.0,
        k=5
    )
    
    print(f"\n🏆 TOP {len(ranked)} Clusters Abiertos (ordenados por score):")
    print("-" * 50)
    
    for i, cluster in enumerate(ranked, 1):
        print(f"{i}. Cluster {cluster['id']}")
        print(f"   Total: {cluster['score_total']:.3f} | "
              f"Trend: {cluster['score_trend']:.2f} | "
              f"Div: {cluster['score_diversity']:.2f} | "
              f"Fresh: {cluster['score_freshness']:.2f}")
        print(f"   Items: {cluster['items_count']} | "
              f"Dominios: {len(cluster['domains'])}")
        print()

def demo_historical_cache():
    """Demuestra el cache de métricas históricas."""
    print("=" * 60)
    print("DEMO: Cache de Métricas Históricas")
    print("=" * 60)
    
    # Crear cache (fallback a memoria si Redis no está disponible)
    cache = HistoricalMetricsCache()
    
    # Simular adición de datos históricos
    cluster_id = 999
    print(f"\n📈 Agregando datos históricos para cluster {cluster_id}:")
    
    counts = [5, 7, 6, 8, 9, 7, 10, 12, 15, 18]
    for day, count in enumerate(counts, 1):
        cache.add_count(cluster_id, count)
        print(f"   Día {day}: {count} items")
    
    # Recuperar historial
    history = cache.get_history(cluster_id)
    print(f"\n📊 Historial recuperado: {history}")
    print(f"   Promedio últimos 7 días: {sum(history[-7:]) / min(7, len(history)):.1f}")
    
    # Mostrar cómo se usaría para trend score
    test_cluster = {'items_count': 20}  # Nuevo count
    trend = trend_spike_score(test_cluster, history)
    print(f"   Trend score con count actual 20: {trend:.3f}")

async def demo_database_integration():
    """Demuestra la integración con base de datos (mock)."""
    print("=" * 60)
    print("DEMO: Integración con Base de Datos")
    print("=" * 60)
    
    clusters = create_sample_clusters()
    historic_data = create_sample_historic_data()
    now = datetime.now(timezone.utc)
    
    # Aplicar scoring
    score_and_rank_clusters(
        clusters, 
        historic_counts_map=historic_data,
        now=now
    )
    
    print("\n💾 Datos listos para persistir en base de datos:")
    for cluster in clusters:
        if 'score_total' in cluster:
            print(f"   Cluster {cluster['id']}:")
            print(f"      score_trend: {cluster['score_trend']:.3f}")
            print(f"      score_diversity: {cluster['score_diversity']:.3f}")
            print(f"      score_freshness: {cluster['score_freshness']:.3f}")
            print(f"      score_total: {cluster['score_total']:.3f}")
    
    # Nota: En una aplicación real, llamarías:
    # await update_cluster_scores_in_db(session, clusters)
    print("\n✅ En producción, estos scores se guardarían en la tabla 'clusters'")

def main():
    """Ejecuta todas las demostraciones."""
    print("🎯 DEMO: Sistema de Scoring para Clusters de Noticias")
    print("WindWorldWire NewsBot - Trender Service")
    
    # Demos síncronos
    demo_individual_scores()
    demo_ranking()
    demo_historical_cache()
    
    # Demo asíncrono
    asyncio.run(demo_database_integration())
    
    print("\n" + "=" * 60)
    print("✅ Demo completado. Las funciones están listas para producción.")
    print("=" * 60)
    
    print("\n📚 Uso en producción:")
    print("```python")
    print("# En el pipeline de trender")
    print("ranked_clusters = score_and_rank_clusters(")
    print("    clusters=active_clusters,")
    print("    now=datetime.now(timezone.utc),")
    print("    tau_hours=3.0,  # Configurable")
    print("    k=10  # Top 10")
    print(")")
    print("")
    print("# Persistir en DB")
    print("await update_cluster_scores_in_db(session, clusters)")
    print("```")

if __name__ == "__main__":
    main()