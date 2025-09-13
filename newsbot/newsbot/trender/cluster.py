"""Clustering incremental para trending topics.

Implementa clustering de contenido usando embeddings de texto para:
- Agrupar artículos similares de forma incremental
- Detectar temas emergentes y trending
- Mantener clusters actualizados en tiempo real
- Calcular centroídes y similarity scores
"""

import asyncio
import time
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN, MiniBatchKMeans
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.core.db import AsyncSessionLocal
from newsbot.core.logging import get_logger
from newsbot.core.repositories import (
    get_recent_raw_items,
    create_cluster,
    add_item_to_cluster,
    get_active_clusters,
    update_cluster_centroid,
    get_cluster_items
)

logger = get_logger(__name__)

# Configuration
DEFAULT_WINDOW_HOURS = 24
MIN_CLUSTER_SIZE = 3
MAX_CLUSTERS = 200
SIMILARITY_THRESHOLD = 0.7
DBSCAN_EPS = 0.3
DBSCAN_MIN_SAMPLES = 2
KMEANS_MAX_CLUSTERS = 50


class ContentEmbedder:
    """Genera embeddings de texto para clustering."""
    
    def __init__(self, max_features: int = 5000):
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.8
        )
        self.is_fitted = False
    
    def fit_transform(self, texts: List[str]) -> np.ndarray:
        """Fit vectorizer and transform texts to embeddings."""
        if not texts:
            return np.array([])
        
        try:
            embeddings = self.vectorizer.fit_transform(texts)
            self.is_fitted = True
            logger.info(f"Fitted embeddings: {embeddings.shape}")
            return embeddings.toarray()
        except Exception as e:
            logger.error(f"Error fitting embeddings: {e}")
            return np.array([])
    
    def transform(self, texts: List[str]) -> np.ndarray:
        """Transform texts to embeddings using fitted vectorizer."""
        if not self.is_fitted:
            raise ValueError("Vectorizer not fitted. Call fit_transform first.")
        
        if not texts:
            return np.array([])
        
        try:
            embeddings = self.vectorizer.transform(texts)
            return embeddings.toarray()
        except Exception as e:
            logger.error(f"Error transforming embeddings: {e}")
            return np.array([])
    
    def get_feature_names(self) -> List[str]:
        """Get feature names from vectorizer."""
        if not self.is_fitted:
            return []
        return self.vectorizer.get_feature_names_out().tolist()


class IncrementalClusterer:
    """Clustering incremental usando DBSCAN y K-means."""
    
    def __init__(self, method: str = "dbscan"):
        self.method = method.lower()
        self.embedder = ContentEmbedder()
        self.cluster_centroids = {}  # cluster_id -> centroid vector
        
    def prepare_content_text(self, item: Dict[str, Any]) -> str:
        """Prepara texto del item para embeddings."""
        parts = []
        
        # Title (weighted more heavily)
        if item.get('title'):
            title = str(item['title']).strip()
            if title:
                parts.append(f"{title} {title}")  # Double weight
        
        # Summary/description
        if item.get('summary'):
            summary = str(item['summary']).strip()
            if summary:
                parts.append(summary)
        
        # Content if available
        if item.get('content'):
            content = str(item['content']).strip()
            if content:
                # Truncate very long content
                parts.append(content[:1000])
        
        return " ".join(parts)
    
    def cluster_dbscan(self, embeddings: np.ndarray) -> np.ndarray:
        """Cluster using DBSCAN algorithm."""
        if embeddings.shape[0] < DBSCAN_MIN_SAMPLES:
            return np.array([-1] * embeddings.shape[0])
        
        try:
            clusterer = DBSCAN(
                eps=DBSCAN_EPS,
                min_samples=DBSCAN_MIN_SAMPLES,
                metric='cosine'
            )
            labels = clusterer.fit_predict(embeddings)
            
            n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
            n_noise = list(labels).count(-1)
            
            logger.info(f"DBSCAN: {n_clusters} clusters, {n_noise} noise points")
            return labels
            
        except Exception as e:
            logger.error(f"DBSCAN clustering failed: {e}")
            return np.array([-1] * embeddings.shape[0])
    
    def cluster_kmeans(self, embeddings: np.ndarray, n_clusters: Optional[int] = None) -> np.ndarray:
        """Cluster using Mini-Batch K-means."""
        if embeddings.shape[0] < 2:
            return np.array([0] * embeddings.shape[0])
        
        if n_clusters is None:
            # Estimate number of clusters
            n_clusters = min(
                max(2, embeddings.shape[0] // 10),
                KMEANS_MAX_CLUSTERS
            )
        
        try:
            clusterer = MiniBatchKMeans(
                n_clusters=n_clusters,
                random_state=42,
                batch_size=100
            )
            labels = clusterer.fit_predict(embeddings)
            
            logger.info(f"K-means: {n_clusters} clusters")
            return labels
            
        except Exception as e:
            logger.error(f"K-means clustering failed: {e}")
            return np.array([0] * embeddings.shape[0])
    
    def calculate_centroid(self, embeddings: np.ndarray) -> np.ndarray:
        """Calculate centroid of embeddings."""
        if embeddings.shape[0] == 0:
            return np.array([])
        return np.mean(embeddings, axis=0)
    
    def find_similar_cluster(self, item_embedding: np.ndarray, 
                           existing_centroids: Dict[int, np.ndarray],
                           threshold: float = SIMILARITY_THRESHOLD) -> Optional[int]:
        """Find most similar existing cluster for new item."""
        if not existing_centroids:
            return None
        
        best_cluster = None
        best_similarity = threshold
        
        for cluster_id, centroid in existing_centroids.items():
            try:
                similarity = cosine_similarity(
                    item_embedding.reshape(1, -1),
                    centroid.reshape(1, -1)
                )[0, 0]
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_cluster = cluster_id
                    
            except Exception as e:
                logger.warning(f"Error calculating similarity with cluster {cluster_id}: {e}")
        
        return best_cluster


async def cluster_recent_content(session: AsyncSession, 
                               window_hours: int = DEFAULT_WINDOW_HOURS,
                               incremental: bool = True) -> Dict[str, Any]:
    """
    Cluster contenido reciente de forma incremental.
    
    Args:
        session: Database session
        window_hours: Ventana de tiempo para contenido reciente
        incremental: Si usar clustering incremental o recrear todo
        
    Returns:
        Dictionary con estadísticas del clustering
    """
    start_time = time.time()
    
    try:
        # Get recent content
        recent_items = await get_recent_raw_items(session, hours=window_hours)
        
        if not recent_items:
            logger.info("No recent content found for clustering")
            return {
                'runtime_seconds': time.time() - start_time,
                'items_processed': 0,
                'clusters_created': 0,
                'clusters_updated': 0,
                'items_clustered': 0
            }
        
        logger.info(f"Found {len(recent_items)} recent items for clustering")
        
        # Initialize clusterer
        clusterer = IncrementalClusterer()
        
        # Prepare text content
        texts = []
        valid_items = []
        
        for item in recent_items:
            text = clusterer.prepare_content_text(item)
            if text.strip():
                texts.append(text)
                valid_items.append(item)
        
        if not texts:
            logger.warning("No valid text content found for clustering")
            return {
                'runtime_seconds': time.time() - start_time,
                'items_processed': len(recent_items),
                'clusters_created': 0,
                'clusters_updated': 0,
                'items_clustered': 0
            }
        
        logger.info(f"Processing {len(texts)} items with valid text content")
        
        # Generate embeddings
        embeddings = clusterer.embedder.fit_transform(texts)
        
        if embeddings.shape[0] == 0:
            logger.error("Failed to generate embeddings")
            return {
                'runtime_seconds': time.time() - start_time,
                'items_processed': len(recent_items),
                'clusters_created': 0,
                'clusters_updated': 0,
                'items_clustered': 0
            }
        
        stats = {
            'runtime_seconds': 0,
            'items_processed': len(recent_items),
            'clusters_created': 0,
            'clusters_updated': 0,
            'items_clustered': 0
        }
        
        if incremental:
            # Incremental clustering
            stats.update(await _incremental_clustering(
                session, valid_items, embeddings, clusterer
            ))
        else:
            # Full re-clustering
            stats.update(await _full_clustering(
                session, valid_items, embeddings, clusterer
            ))
        
        stats['runtime_seconds'] = time.time() - start_time
        
        logger.info(
            f"Clustering completed: {stats['clusters_created']} new clusters, "
            f"{stats['clusters_updated']} updated, {stats['items_clustered']} items clustered"
        )
        
        return stats
        
    except Exception as e:
        logger.error(f"Clustering failed: {e}")
        return {
            'runtime_seconds': time.time() - start_time,
            'items_processed': 0,
            'clusters_created': 0,
            'clusters_updated': 0,
            'items_clustered': 0,
            'error': str(e)
        }


async def _incremental_clustering(session: AsyncSession,
                                items: List[Dict[str, Any]],
                                embeddings: np.ndarray,
                                clusterer: IncrementalClusterer) -> Dict[str, Any]:
    """Perform incremental clustering with existing clusters."""
    
    # Get existing active clusters and their centroids
    existing_clusters = await get_active_clusters(session)
    existing_centroids = {}
    
    for cluster in existing_clusters:
        if cluster.centroid_vector:
            try:
                # Deserialize centroid vector (assuming it's stored as JSON)
                import json
                centroid = np.array(json.loads(cluster.centroid_vector))
                existing_centroids[cluster.id] = centroid
            except Exception as e:
                logger.warning(f"Failed to load centroid for cluster {cluster.id}: {e}")
    
    clusters_created = 0
    clusters_updated = 0
    items_clustered = 0
    
    # Process each item incrementally
    for i, (item, embedding) in enumerate(zip(items, embeddings)):
        try:
            # Find similar existing cluster
            similar_cluster_id = clusterer.find_similar_cluster(
                embedding, existing_centroids
            )
            
            if similar_cluster_id:
                # Add to existing cluster
                await add_item_to_cluster(session, similar_cluster_id, item['id'])
                
                # Update centroid
                cluster_items = await get_cluster_items(session, similar_cluster_id)
                if cluster_items:
                    # Recalculate centroid
                    cluster_embeddings = []
                    for cluster_item in cluster_items:
                        item_text = clusterer.prepare_content_text(cluster_item)
                        if item_text:
                            item_emb = clusterer.embedder.transform([item_text])
                            if item_emb.shape[0] > 0:
                                cluster_embeddings.append(item_emb[0])
                    
                    if cluster_embeddings:
                        new_centroid = np.mean(cluster_embeddings, axis=0)
                        existing_centroids[similar_cluster_id] = new_centroid
                        
                        # Update in database
                        import json
                        await update_cluster_centroid(
                            session, similar_cluster_id, json.dumps(new_centroid.tolist())
                        )
                        
                        clusters_updated += 1
                
                items_clustered += 1
                
            else:
                # Create new cluster
                cluster_id = await create_cluster(
                    session,
                    name=f"cluster_{int(time.time())}_{i}",
                    centroid_vector=None,  # Will be set below
                    created_at=datetime.now(timezone.utc)
                )
                
                if cluster_id:
                    # Add item to new cluster
                    await add_item_to_cluster(session, cluster_id, item['id'])
                    
                    # Set centroid
                    import json
                    centroid_json = json.dumps(embedding.tolist())
                    await update_cluster_centroid(session, cluster_id, centroid_json)
                    
                    existing_centroids[cluster_id] = embedding
                    clusters_created += 1
                    items_clustered += 1
                
        except Exception as e:
            logger.error(f"Error processing item {item.get('id', 'unknown')}: {e}")
    
    return {
        'clusters_created': clusters_created,
        'clusters_updated': clusters_updated,
        'items_clustered': items_clustered
    }


async def _full_clustering(session: AsyncSession,
                         items: List[Dict[str, Any]],
                         embeddings: np.ndarray,
                         clusterer: IncrementalClusterer) -> Dict[str, Any]:
    """Perform full clustering from scratch."""
    
    # Perform clustering
    if clusterer.method == "dbscan":
        labels = clusterer.cluster_dbscan(embeddings)
    else:
        labels = clusterer.cluster_kmeans(embeddings)
    
    clusters_created = 0
    items_clustered = 0
    
    # Group items by cluster
    cluster_groups = {}
    for i, label in enumerate(labels):
        if label >= 0:  # Skip noise points (-1)
            if label not in cluster_groups:
                cluster_groups[label] = []
            cluster_groups[label].append((items[i], embeddings[i]))
    
    # Create clusters in database
    for cluster_label, cluster_items in cluster_groups.items():
        if len(cluster_items) < MIN_CLUSTER_SIZE:
            continue
        
        try:
            # Calculate centroid
            cluster_embeddings = [emb for _, emb in cluster_items]
            centroid = clusterer.calculate_centroid(np.array(cluster_embeddings))
            
            # Create cluster
            cluster_id = await create_cluster(
                session,
                name=f"cluster_{cluster_label}_{int(time.time())}",
                centroid_vector=None,
                created_at=datetime.now(timezone.utc)
            )
            
            if cluster_id:
                # Add items to cluster
                for item, _ in cluster_items:
                    await add_item_to_cluster(session, cluster_id, item['id'])
                    items_clustered += 1
                
                # Set centroid
                import json
                centroid_json = json.dumps(centroid.tolist())
                await update_cluster_centroid(session, cluster_id, centroid_json)
                
                clusters_created += 1
                
        except Exception as e:
            logger.error(f"Error creating cluster {cluster_label}: {e}")
    
    return {
        'clusters_created': clusters_created,
        'clusters_updated': 0,
        'items_clustered': items_clustered
    }


async def run_clustering_pipeline(window_hours: int = DEFAULT_WINDOW_HOURS,
                                incremental: bool = True) -> Dict[str, Any]:
    """
    Run complete clustering pipeline.
    
    Args:
        window_hours: Ventana de tiempo para contenido
        incremental: Si usar clustering incremental
        
    Returns:
        Estadísticas del clustering
    """
    async with AsyncSessionLocal() as session:
        return await cluster_recent_content(
            session,
            window_hours=window_hours,
            incremental=incremental
        )