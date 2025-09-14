#!/usr/bin/env python3
"""Demo del pipeline orquestador completo.

Prueba las funciones principales run_trending() y run_topics() 
del pipeline orquestador.
"""

import asyncio
import time
from newsbot.trender.pipeline import run_trending, run_topics


async def demo_orchestrator_pipeline():
    """Demo del pipeline orquestador."""
    
    print("🎭 Demo: Pipeline Orquestador Completo")
    print("=" * 60)
    
    # Test 1: Global trending pipeline
    print("🌍 Test 1: Pipeline de Trending Global")
    print("-" * 40)
    
    try:
        start_time = time.time()
        selection = await run_trending(window_hours=24, k_global=10)
        runtime = time.time() - start_time
        
        print(f"✅ Pipeline global completado en {runtime:.2f}s")
        print(f"  📊 Picks globales: {len(selection.global_picks)}")
        print(f"  🏷️  Picks por tema: {len(selection.topic_picks)}")
        print(f"  📈 Total picks: {selection.total_picks}")
        
        if selection.global_picks:
            print(f"  🥇 Top global pick: Cluster {selection.global_picks[0].cluster_id} "
                  f"(score: {selection.global_picks[0].score_total:.3f})")
        
        if selection.topic_picks:
            print(f"  🎯 Top topic pick: Cluster {selection.topic_picks[0].cluster_id} "
                  f"(topic: {selection.topic_picks[0].topic_key}, "
                  f"adjusted_score: {selection.topic_picks[0].adjusted_score:.3f})")
        
    except Exception as e:
        print(f"❌ Pipeline global falló: {e}")
    
    print()
    
    # Test 2: Per-topic analysis pipeline
    print("🏷️ Test 2: Pipeline de Análisis por Temas")
    print("-" * 40)
    
    try:
        start_time = time.time()
        topics_results = await run_topics(window_hours=24)
        runtime = time.time() - start_time
        
        print(f"✅ Pipeline por temas completado en {runtime:.2f}s")
        print(f"  📁 Temas procesados: {len(topics_results)}")
        
        total_topic_picks = 0
        total_global_picks = 0
        
        for topic_key, selection in topics_results.items():
            topic_picks = len(selection.topic_picks)
            global_picks = len(selection.global_picks)
            total_topic_picks += topic_picks
            total_global_picks += global_picks
            
            print(f"    • {topic_key}: {topic_picks} topic + {global_picks} global picks")
            
            # Show top pick for this topic if available
            if selection.topic_picks:
                top_pick = selection.topic_picks[0]
                print(f"      🥇 Top: Cluster {top_pick.cluster_id} "
                      f"(score: {top_pick.adjusted_score:.3f})")
        
        print(f"  📊 Total: {total_topic_picks} topic picks + {total_global_picks} global picks")
        
    except Exception as e:
        print(f"❌ Pipeline por temas falló: {e}")
    
    print()
    
    # Test 3: Performance comparison
    print("⚡ Test 3: Comparación de Performance")
    print("-" * 40)
    
    try:
        # Test both pipelines with smaller window for speed
        print("Ejecutando ambos pipelines con ventana de 6 horas...")
        
        # Global trending
        start_global = time.time()
        global_selection = await run_trending(window_hours=6, k_global=5)
        global_time = time.time() - start_global
        
        # Per-topic analysis
        start_topics = time.time()
        topics_results = await run_topics(window_hours=6)
        topics_time = time.time() - start_topics
        
        print(f"  🌍 Global trending: {global_time:.2f}s → {global_selection.total_picks} picks")
        print(f"  🏷️  Per-topic analysis: {topics_time:.2f}s → {len(topics_results)} topics")
        
        # Calculate efficiency
        if global_time > 0 and topics_time > 0:
            if global_time < topics_time:
                faster = "Global"
                ratio = topics_time / global_time
            else:
                faster = "Topics"  
                ratio = global_time / topics_time
            
            print(f"  ⚡ {faster} pipeline is {ratio:.1f}x más rápido")
        
    except Exception as e:
        print(f"❌ Comparación de performance falló: {e}")
    
    print()
    print("🎉 Demo del pipeline orquestador completado!")


if __name__ == "__main__":
    asyncio.run(demo_orchestrator_pipeline())