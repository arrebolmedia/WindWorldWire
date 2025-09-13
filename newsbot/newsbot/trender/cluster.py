"""
Incremental semantic clustering for raw items using embeddings.
"""

import os
import hashlib
import json
import numpy as np
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlparse

from newsbot.core.logging import get_logger
from newsbot.core.db import AsyncSessionLocal
from newsbot.core.repositories import (
    get_recent_raw_items
)

logger = get_logger(__name__)


@dataclass
class ClusterStats:
    """Statistics for clustering operation."""
    total_items: int
    new_clusters: int
    existing_clusters: int
    items_clustered: int
    processing_time: float


class Embedder(ABC):
    """Abstract base class for text embeddings."""
    
    @abstractmethod
    def embed(self, texts: List[str]) -> np.ndarray:
        """
        Embed a list of texts into vectors.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            Numpy array of shape (len(texts), embedding_dim)
        """
        pass
    
    @property
    @abstractmethod
    def embedding_dim(self) -> int:
        """Return the dimensionality of embeddings."""
        pass


class SentenceTransformersEmbedder(Embedder):
    """Real embedder using SentenceTransformers."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize SentenceTransformers embedder.
        
        Args:
            model_name: Name of the SentenceTransformers model to use
        """
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self._embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(f"Initialized SentenceTransformers embedder: {model_name}")
        except ImportError:
            raise ImportError(
                "SentenceTransformers not available. Install with: "
                "pip install sentence-transformers"
            )
    
    def embed(self, texts: List[str]) -> np.ndarray:
        """Embed texts using SentenceTransformers."""
        if not texts:
            return np.array([]).reshape(0, self.embedding_dim)
        
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings
    
    @property
    def embedding_dim(self) -> int:
        """Return embedding dimensionality."""
        return self._embedding_dim


class DummyEmbedder(Embedder):
    """Dummy embedder for testing - generates deterministic vectors from text hash."""
    
    def __init__(self, embedding_dim: int = 384):
        """
        Initialize dummy embedder.
        
        Args:
            embedding_dim: Dimensionality of fake embeddings
        """
        self._embedding_dim = embedding_dim
        logger.info(f"Initialized dummy embedder (dim={embedding_dim})")
    
    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate deterministic embeddings from text hash."""
        if not texts:
            return np.array([]).reshape(0, self.embedding_dim)
        
        embeddings = []
        for text in texts:
            # Generate deterministic vector from text hash
            text_hash = hashlib.sha1(text.encode('utf-8')).hexdigest()
            
            # Convert hex to numbers and normalize
            hex_nums = [int(text_hash[i:i+2], 16) for i in range(0, len(text_hash), 2)]
            
            # Repeat/truncate to get desired dimension
            vector = []
            for i in range(self.embedding_dim):
                vector.append(hex_nums[i % len(hex_nums)] / 255.0)
            
            # Normalize to unit vector
            vector = np.array(vector)
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = vector / norm
            
            embeddings.append(vector)
        
        return np.array(embeddings)
    
    @property
    def embedding_dim(self) -> int:
        """Return embedding dimensionality."""
        return self._embedding_dim


@dataclass
class ClusterInfo:
    """Information about a cluster."""
    id: int
    centroid: np.ndarray
    first_seen: datetime
    last_seen: datetime
    items_count: int
    domains_count: int
    domains: Dict[str, int]
    topic_key: Optional[str] = None


class IncrementalClusterer:
    """Incremental semantic clustering for news items."""
    
    def __init__(self, 
                 embedder: Optional[Embedder] = None,
                 similarity_threshold: float = None):
        """
        Initialize incremental clusterer.
        
        Args:
            embedder: Embedder instance (defaults to auto-detect)
            similarity_threshold: Cosine similarity threshold for cluster assignment
        """
        # Set similarity threshold from env or default
        self.similarity_threshold = similarity_threshold or float(
            os.getenv("CLUSTERING_SIMILARITY_THRESHOLD", "0.78")
        )
        
        # Initialize embedder
        if embedder is None:
            self.embedder = self._create_default_embedder()
        else:
            self.embedder = embedder
        
        # In-memory cluster cache
        self.clusters: Dict[int, ClusterInfo] = {}
        
        logger.info(
            f"Initialized incremental clusterer "
            f"(threshold={self.similarity_threshold}, embedder={type(self.embedder).__name__})"
        )
    
    def _create_default_embedder(self) -> Embedder:
        """Create default embedder with fallback."""
        try:
            return SentenceTransformersEmbedder()
        except ImportError:
            logger.warning(
                "SentenceTransformers not available, using dummy embedder. "
                "Install with: pip install sentence-transformers"
            )
            return DummyEmbedder()
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except:
            return "unknown"
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def _find_best_cluster(self, item_embedding: np.ndarray) -> Tuple[Optional[int], float]:
        """
        Find the best matching cluster for an item.
        
        Args:
            item_embedding: Embedding vector for the item
            
        Returns:
            Tuple of (cluster_id, similarity_score) or (None, 0.0)
        """
        best_cluster_id = None
        best_similarity = 0.0
        
        for cluster_id, cluster_info in self.clusters.items():
            similarity = self._cosine_similarity(item_embedding, cluster_info.centroid)
            
            if similarity > best_similarity and similarity >= self.similarity_threshold:
                best_similarity = similarity
                best_cluster_id = cluster_id
        
        return best_cluster_id, best_similarity
    
    def _update_cluster_centroid(self, cluster_id: int, new_embedding: np.ndarray):
        """Update cluster centroid with new item embedding."""
        if cluster_id not in self.clusters:
            return
        
        cluster_info = self.clusters[cluster_id]
        current_count = cluster_info.items_count
        current_centroid = cluster_info.centroid
        
        # Compute running average of embeddings
        updated_centroid = (
            (current_centroid * current_count + new_embedding) / (current_count + 1)
        )
        
        # Normalize to unit vector
        norm = np.linalg.norm(updated_centroid)
        if norm > 0:
            updated_centroid = updated_centroid / norm
        
        cluster_info.centroid = updated_centroid
    
    async def load_existing_clusters(self, window_hours: int = 72):
        """
        Load existing clusters from database.
        
        Args:
            window_hours: Only load clusters from this time window
        """
        async with AsyncSessionLocal() as session:
            from newsbot.core.models import Cluster
            from sqlalchemy import select
            from datetime import timedelta
            
            # Load clusters from the specified time window
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=window_hours)
            
            stmt = select(Cluster).where(
                Cluster.first_seen >= cutoff_time
            ).where(
                Cluster.status == 'open'
            )
            
            result = await session.execute(stmt)
            clusters = result.scalars().all()
            
            for cluster in clusters:
                # Parse centroid from database
                centroid = None
                if cluster.centroid and len(cluster.centroid) > 0:
                    try:
                        centroid = np.array(cluster.centroid)
                    except:
                        logger.warning(f"Could not parse centroid for cluster {cluster.id}")
                        continue
                
                if centroid is None:
                    # Skip clusters without valid centroids
                    continue
                
                # Extract domain counts
                domains = cluster.domains or {}
                if isinstance(domains, str):
                    try:
                        domains = json.loads(domains)
                    except:
                        domains = {}
                
                cluster_info = ClusterInfo(
                    id=cluster.id,
                    centroid=centroid,
                    first_seen=cluster.first_seen,
                    last_seen=cluster.last_seen,
                    items_count=cluster.items_count,
                    domains_count=cluster.domains_count,
                    domains=domains,
                    topic_key=cluster.topic_key
                )
                
                self.clusters[cluster.id] = cluster_info
        
        logger.info(f"Loaded {len(self.clusters)} existing clusters")
    
    async def cluster_recent_items(self, window_hours: int = 24) -> ClusterStats:
        """
        Cluster recent raw items.
        
        Args:
            window_hours: Look back this many hours for items
            
        Returns:
            ClusterStats with operation results
        """
        start_time = datetime.now()
        
        # Load existing clusters
        await self.load_existing_clusters(window_hours * 3)  # Load wider window for clusters
        
        # Get recent items
        async with AsyncSessionLocal() as session:
            recent_items = await get_recent_raw_items(session, hours=window_hours)
        
        if not recent_items:
            logger.info("No recent items to cluster")
            return ClusterStats(
                total_items=0,
                new_clusters=0,
                existing_clusters=len(self.clusters),
                items_clustered=0,
                processing_time=0.0
            )
        
        # Prepare texts for embedding
        texts = []
        for item in recent_items:
            # Combine title and summary for embedding
            text_parts = [item['title']]
            if item.get('summary'):
                text_parts.append(item['summary'])
            
            text = ' '.join(text_parts).strip()
            texts.append(text)
        
        # Generate embeddings
        logger.info(f"Generating embeddings for {len(texts)} items")
        embeddings = self.embedder.embed(texts)
        
        # Process each item
        new_clusters = 0
        items_clustered = 0
        
        for i, (item, embedding) in enumerate(zip(recent_items, embeddings)):
            try:
                # Find best cluster
                best_cluster_id, similarity = self._find_best_cluster(embedding)
                
                if best_cluster_id is not None:
                    # Add to existing cluster
                    cluster_id = best_cluster_id
                    logger.debug(f"Item {item['id']} -> cluster {cluster_id} (sim={similarity:.3f})")
                else:
                    # Create new cluster
                    cluster_id = await self._create_new_cluster(item, embedding)
                    new_clusters += 1
                    logger.debug(f"Item {item['id']} -> new cluster {cluster_id}")
                
                if cluster_id:
                    # Add item to cluster
                    await self._add_item_to_cluster(cluster_id, item, similarity)
                    items_clustered += 1
                
            except Exception as e:
                logger.error(f"Error clustering item {item['id']}: {e}")
                continue
        
        # Update cluster centroids in database
        await self._persist_cluster_centroids()
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        stats = ClusterStats(
            total_items=len(recent_items),
            new_clusters=new_clusters,
            existing_clusters=len(self.clusters) - new_clusters,
            items_clustered=items_clustered,
            processing_time=processing_time
        )
        
        logger.info(
            f"Clustering completed: {stats.items_clustered}/{stats.total_items} items, "
            f"{stats.new_clusters} new clusters, {stats.processing_time:.2f}s"
        )
        
        return stats
    
    async def _create_new_cluster(self, item: Dict[str, Any], embedding: np.ndarray) -> Optional[int]:
        """Create a new cluster for an item."""
        try:
            # Extract domain
            domain = self._extract_domain(item['url'])
            
            # Create cluster in database
            async with AsyncSessionLocal() as session:
                from newsbot.core.models import Cluster
                from sqlalchemy import insert
                
                cluster_data = {
                    'centroid': embedding.tolist(),
                    'first_seen': item['published_at'] or item['fetched_at'],
                    'last_seen': item['published_at'] or item['fetched_at'],
                    'items_count': 0,
                    'domains_count': 1 if domain != "unknown" else 0,
                    'domains': {domain: 1} if domain != "unknown" else {},
                    'score_trend': 0.0,
                    'score_fresh': 0.0,
                    'score_diversity': 0.0,
                    'score_total': 0.0,
                    'status': 'open'
                }
                
                stmt = insert(Cluster).values(**cluster_data)
                result = await session.execute(stmt)
                await session.commit()
                
                cluster_id = result.inserted_primary_key[0]
            
            if cluster_id:
                # Add to in-memory cache
                cluster_info = ClusterInfo(
                    id=cluster_id,
                    centroid=embedding / np.linalg.norm(embedding),  # Normalize
                    first_seen=item['published_at'] or item['fetched_at'],
                    last_seen=item['published_at'] or item['fetched_at'],
                    items_count=0,
                    domains_count=1 if domain != "unknown" else 0,
                    domains={domain: 1} if domain != "unknown" else {}
                )
                
                self.clusters[cluster_id] = cluster_info
                
                return cluster_id
                
        except Exception as e:
            logger.error(f"Error creating new cluster for item {item['id']}: {e}")
            return None
    
    async def _add_item_to_cluster(self, cluster_id: int, item: Dict[str, Any], similarity: float):
        """Add an item to a cluster."""
        try:
            # Add to database
            async with AsyncSessionLocal() as session:
                domain = self._extract_domain(item['url'])
                
                from newsbot.core.models import ClusterItem
                from sqlalchemy import insert
                
                cluster_item_data = {
                    'cluster_id': cluster_id,
                    'raw_item_id': item['id'],
                    'source_domain': domain,
                    'similarity': similarity,
                    'created_at': datetime.now(timezone.utc)
                }
                
                stmt = insert(ClusterItem).values(**cluster_item_data)
                await session.execute(stmt)
                await session.commit()
                
                if cluster_id in self.clusters:
                    # Update in-memory cluster info
                    cluster_info = self.clusters[cluster_id]
                    cluster_info.items_count += 1
                    cluster_info.last_seen = max(
                        cluster_info.last_seen,
                        item['published_at'] or item['fetched_at']
                    )
                    
                    # Update domain counts
                    if domain != "unknown":
                        if domain in cluster_info.domains:
                            cluster_info.domains[domain] += 1
                        else:
                            cluster_info.domains[domain] = 1
                            cluster_info.domains_count += 1
                
        except Exception as e:
            logger.error(f"Error adding item {item['id']} to cluster {cluster_id}: {e}")
    
    async def _persist_cluster_centroids(self):
        """Persist updated cluster centroids to database."""
        async with AsyncSessionLocal() as session:
            for cluster_id, cluster_info in self.clusters.items():
                try:
                    from newsbot.core.models import Cluster
                    from sqlalchemy import update
                    
                    stmt = update(Cluster).where(
                        Cluster.id == cluster_id
                    ).values(
                        centroid=cluster_info.centroid.tolist(),
                        items_count=cluster_info.items_count,
                        domains_count=cluster_info.domains_count,
                        domains=cluster_info.domains,
                        last_seen=cluster_info.last_seen
                    )
                    
                    await session.execute(stmt)
                    await session.commit()
                    
                except Exception as e:
                    logger.error(f"Error persisting centroid for cluster {cluster_id}: {e}")
    
    def get_cluster_ids(self) -> List[int]:
        """Get list of all cluster IDs."""
        return list(self.clusters.keys())
    
    def get_cluster_info(self, cluster_id: int) -> Optional[ClusterInfo]:
        """Get information about a specific cluster."""
        return self.clusters.get(cluster_id)


# Main clustering function for external use
async def cluster_recent_items(window_hours: int = 24, 
                             similarity_threshold: float = None) -> Dict[str, Any]:
    """
    Cluster recent raw items and return results.
    
    Args:
        window_hours: How many hours back to look for items
        similarity_threshold: Cosine similarity threshold for clustering
        
    Returns:
        Dictionary with clustering results and statistics
    """
    clusterer = IncrementalClusterer(similarity_threshold=similarity_threshold)
    stats = await clusterer.cluster_recent_items(window_hours)
    
    return {
        "cluster_ids": clusterer.get_cluster_ids(),
        "stats": {
            "total_items": stats.total_items,
            "new_clusters": stats.new_clusters,
            "existing_clusters": stats.existing_clusters,
            "items_clustered": stats.items_clustered,
            "processing_time": stats.processing_time
        }
    }


if __name__ == "__main__":
    import asyncio
    
    async def main():
        """Test clustering with recent items."""
        print("Starting clustering test...")
        
        result = await cluster_recent_items(window_hours=24)
        
        print(f"Clustering results:")
        print(f"  - Total clusters: {len(result['cluster_ids'])}")
        print(f"  - Stats: {result['stats']}")
        
        for cluster_id in result['cluster_ids'][:5]:  # Show first 5
            print(f"  - Cluster {cluster_id}")
    
    asyncio.run(main())