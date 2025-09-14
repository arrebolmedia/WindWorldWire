#!/usr/bin/env python3
"""Demo completo del sistema de selección final de picks.

Demuestra el flujo completo desde clusters scored hasta selección final,
incluyendo políticas globales, por tema, y eliminación de duplicados.
"""

import asyncio
import numpy as np
from newsbot.trender import (
    PickSelector, Selection, ClusterMetrics, TopicConfig, run_final_selection
)


async def demo_complete_selection_pipeline():
    """Demo del pipeline completo de selección."""
    
    print("🎯 Demo: Sistema de Selección Final de Picks")
    print("=" * 60)
    
    # Mock scored clusters (simulando resultados del scoring)
    print("📊 Clusters scored disponibles:")
    scored_clusters = [
        ClusterMetrics(
            cluster_id=101, viral_score=0.9, freshness_score=0.8, 
            diversity_score=0.7, volume_score=0.8, quality_score=0.9,
            composite_score=0.92, item_count=12, avg_age_hours=1.5,
            unique_sources=8, unique_domains=5
        ),
        ClusterMetrics(
            cluster_id=102, viral_score=0.8, freshness_score=0.9, 
            diversity_score=0.8, volume_score=0.7, quality_score=0.8,
            composite_score=0.88, item_count=8, avg_age_hours=2.0,
            unique_sources=6, unique_domains=4
        ),
        ClusterMetrics(
            cluster_id=103, viral_score=0.7, freshness_score=0.7, 
            diversity_score=0.9, volume_score=0.9, quality_score=0.7,
            composite_score=0.85, item_count=15, avg_age_hours=3.0,
            unique_sources=10, unique_domains=6
        ),
        ClusterMetrics(
            cluster_id=104, viral_score=0.6, freshness_score=0.8, 
            diversity_score=0.6, volume_score=0.6, quality_score=0.9,
            composite_score=0.75, item_count=5, avg_age_hours=4.0,
            unique_sources=4, unique_domains=3
        ),
        ClusterMetrics(
            cluster_id=105, viral_score=0.8, freshness_score=0.6, 
            diversity_score=0.5, volume_score=0.8, quality_score=0.6,
            composite_score=0.70, item_count=6, avg_age_hours=5.0,
            unique_sources=5, unique_domains=3
        )
    ]
    
    for cluster in scored_clusters:
        print(f"  • Cluster {cluster.cluster_id}: score={cluster.composite_score:.3f}, "
              f"items={cluster.item_count}, sources={cluster.unique_sources}")
    
    # Mock cluster-topic mapping (simulando resultados del topic matching)
    print(f"\n🏷️  Asignación cluster → tema:")
    cluster_topic_mapping = {
        101: 'taiwan_seguridad',      # Alto score, alta prioridad
        102: 'taiwan_seguridad',      # Alto score, alta prioridad
        103: 'empresas-negocios',     # Alto score, baja prioridad
        104: 'tecnologia-fintech',    # Medio score, media prioridad
        # 105 sin tema (solo global)
    }
    
    for cluster_id, topic in cluster_topic_mapping.items():
        print(f"  • Cluster {cluster_id} → {topic}")
    print(f"  • Cluster 105 → (sin tema, solo global)")
    
    # Mock centroids (simulando vectores de clustering)
    print(f"\n🎯 Centroides para detección de duplicados:")
    cluster_centroids = {
        101: np.array([0.8, 0.1, 0.1, 0.0]),  # Taiwan security
        102: np.array([0.75, 0.15, 0.1, 0.0]), # Taiwan security (similar a 101)
        103: np.array([0.1, 0.8, 0.1, 0.0]),  # Business
        104: np.array([0.0, 0.1, 0.8, 0.1]),  # Tech
        105: np.array([0.2, 0.2, 0.2, 0.4])   # General
    }
    
    # Calcular similaridades para mostrar
    selector = PickSelector()
    sim_101_102 = selector.calculate_centroid_similarity(101, 102, cluster_centroids)
    print(f"  • Similaridad cluster 101 ↔ 102: {sim_101_102:.3f} "
          f"({'duplicado' if sim_101_102 >= 0.9 else 'diferente'})")
    
    # Configuración sources.yaml simulada
    sources_config = {
        'k_global': 10,           # Top 10 global
        'max_posts_per_run': 50   # Límite máximo 50 posts
    }
    
    print(f"\n⚙️  Configuración global:")
    print(f"  • k_global: {sources_config['k_global']}")
    print(f"  • max_posts_per_run: {sources_config['max_posts_per_run']}")
    
    # Topics configuration simulada
    topics_config = [
        TopicConfig(
            name="Taiwán y seguridad regional",
            topic_key="taiwan_seguridad",
            queries=['"Taiwan"'],
            priority=0.9,           # Alta prioridad
            max_posts_per_run=3,    # Hasta 3 posts
            enabled=True
        ),
        TopicConfig(
            name="Empresas y Negocios", 
            topic_key="empresas-negocios",
            queries=['"business"'],
            priority=0.5,           # Baja prioridad
            max_posts_per_run=2,    # Hasta 2 posts
            enabled=True
        ),
        TopicConfig(
            name="Tecnología y Fintech",
            topic_key="tecnologia-fintech", 
            queries=['"fintech"'],
            priority=0.7,           # Media prioridad
            max_posts_per_run=2,    # Hasta 2 posts
            enabled=True
        )
    ]
    
    print(f"\n📋 Configuración de temas:")
    for topic in topics_config:
        print(f"  • {topic.name}: priority={topic.priority}, max_posts={topic.max_posts_per_run}")
    
    # EJECUTAR SELECCIÓN FINAL
    print(f"\n🚀 Ejecutando selección final...")
    print("-" * 60)
    
    selection = selector.select_final_picks(
        scored_clusters=scored_clusters,
        sources_config=sources_config,
        topics_config=topics_config,
        cluster_topic_mapping=cluster_topic_mapping,
        cluster_centroids=cluster_centroids
    )
    
    # MOSTRAR RESULTADOS
    print(f"\n📊 RESULTADOS DE SELECCIÓN:")
    print("=" * 60)
    
    print(f"\n🌍 PICKS GLOBALES ({len(selection.global_picks)}):")
    if selection.global_picks:
        for i, pick in enumerate(selection.global_picks):
            print(f"  {i+1}. Cluster {pick.cluster_id}")
            print(f"     Score: {pick.score_total:.3f}")
            print(f"     Rank: {pick.rank}")
            print()
    else:
        print("  (Ninguno - todos fueron superados por picks de tema)")
    
    print(f"🏷️  PICKS POR TEMA ({len(selection.topic_picks)}):")
    if selection.topic_picks:
        # Agrupar por tema
        by_topic = {}
        for pick in selection.topic_picks:
            if pick.topic_key not in by_topic:
                by_topic[pick.topic_key] = []
            by_topic[pick.topic_key].append(pick)
        
        for topic_key, picks in by_topic.items():
            topic_config = next((t for t in topics_config if t.topic_key == topic_key), None)
            topic_name = topic_config.name if topic_config else topic_key
            print(f"\n  📁 {topic_name} ({len(picks)} picks):")
            
            for pick in picks:
                print(f"    • Cluster {pick.cluster_id}")
                print(f"      Score original: {pick.score_total:.3f}")
                print(f"      Score ajustado: {pick.adjusted_score:.3f} "
                      f"(= {pick.score_total:.3f} × {pick.topic_priority:.1f})")
                print(f"      Rank en tema: {pick.rank}")
                print()
    else:
        print("  (Ninguno)")
    
    # ESTADÍSTICAS FINALES
    print(f"📈 ESTADÍSTICAS:")
    print(f"  • Total clusters analizados: {len(scored_clusters)}")
    print(f"  • Clusters con tema asignado: {len(cluster_topic_mapping)}")
    print(f"  • Picks globales finales: {len(selection.global_picks)}")
    print(f"  • Picks por tema finales: {len(selection.topic_picks)}")
    print(f"  • Total picks seleccionados: {selection.total_picks}")
    
    # Verificar duplicados eliminados
    total_initial = len(scored_clusters) + len([c for c in scored_clusters if c.cluster_id in cluster_topic_mapping])
    duplicates_removed = total_initial - selection.total_picks
    print(f"  • Duplicados eliminados: {duplicates_removed}")
    
    print(f"\n✅ Selección final completada!")
    return selection


if __name__ == "__main__":
    asyncio.run(demo_complete_selection_pipeline())