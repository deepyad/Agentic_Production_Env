"""RAG service interface and implementations. Production uses Weaviate."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class RAGChunk:
    """A retrieved document chunk."""
    content: str
    source: Optional[str] = None
    score: Optional[float] = None


class RAGService(ABC):
    """Interface for RAG retrieval. Production: Weaviate."""

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict] = None) -> list[RAGChunk]:
        """Retrieve relevant chunks for a query."""
        pass


class StubRAGService(RAGService):
    """Stub: returns fake chunks. Use WeaviateRAGService in production with Weaviate."""

    def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict] = None) -> list[RAGChunk]:
        return [
            RAGChunk(
                content=f"Stub context for: {query[:50]}...",
                source="stub_doc_1",
                score=0.95,
            ),
        ][:top_k]


class WeaviateRAGService(RAGService):
    """
    Production RAG using Weaviate. Requires weaviate-client.
    Set WEAVIATE_URL (e.g. http://localhost:8080) and optionally WEAVIATE_INDEX.
    """

    def __init__(self, url: str, index_name: str = "RAGChunks") -> None:
        self.url = url
        self.index_name = index_name
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import weaviate
                from urllib.parse import urlparse
                p = urlparse(self.url)
                host = p.hostname or "localhost"
                port = p.port or 8080
                secure = p.scheme == "https"
                if host in ("localhost", "127.0.0.1"):
                    self._client = weaviate.connect_to_local(host=host, port=port, grpc_port=50051)
                else:
                    self._client = weaviate.connect_to_custom(
                        http_host=host,
                        http_port=port,
                        http_secure=secure,
                    )
            except ImportError as e:
                raise RuntimeError("Weaviate required. Install: pip install weaviate-client") from e
            except Exception as e:
                raise RuntimeError(f"Weaviate connection failed: {e}") from e
        return self._client

    def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict] = None) -> list[RAGChunk]:
        """Query Weaviate for relevant chunks (near_text semantic search)."""
        try:
            client = self._get_client()
            collection = client.collections.get(self.index_name)
            response = collection.query.near_text(query=query, limit=top_k)
            chunks = []
            for obj in response.objects:
                props = obj.properties or {}
                content = props.get("content", "") or ""
                source = props.get("source")
                chunks.append(RAGChunk(content=content, source=source, score=getattr(obj.metadata, "score", None)))
            return chunks if chunks else [RAGChunk(content=f"No Weaviate results for: {query[:50]}...", source=None, score=0.0)]
        except Exception as e:
            return [RAGChunk(content=f"Weaviate retrieval error: {e}", source=None, score=0.0)]
