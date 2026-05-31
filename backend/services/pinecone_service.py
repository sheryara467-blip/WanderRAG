from functools import lru_cache
from pinecone import Pinecone, ServerlessSpec
from config import get_settings

settings = get_settings()


@lru_cache(maxsize=1)
def get_pinecone_service() -> "PineconeService":
    return PineconeService()


class PineconeService:
    def __init__(self):
        self.pc    = Pinecone(api_key=settings.pinecone_api_key)
        self.index = self._get_or_create_index()

    # -----------------------------------------------------------------------
    # Index management
    # -----------------------------------------------------------------------
    def _get_or_create_index(self):
        existing = [i.name for i in self.pc.list_indexes()]

        if settings.pinecone_index_name not in existing:
            print(f"📦 Creating Pinecone index: {settings.pinecone_index_name}")
            self.pc.create_index(
                name      = settings.pinecone_index_name,
                dimension = settings.embedding_dimension,
                metric    = "cosine",
                spec      = ServerlessSpec(cloud="aws", region="us-east-1"),
            )
            print("✅ Index created")

        return self.pc.Index(settings.pinecone_index_name)

    # -----------------------------------------------------------------------
    # Write operations
    # -----------------------------------------------------------------------
    def upsert_vectors(self, vectors: list[dict]):
        """
        vectors: list of dicts with keys: id, values, metadata
        Pinecone upsert is idempotent — safe to call for both new and updated records.
        Batches of 100 to stay within Pinecone free-tier request limits.
        """
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i : i + batch_size]
            self.index.upsert(vectors=batch)

    def delete_vectors(self, vector_ids: list[str]):
        """Delete vectors by their IDs. Called for removed places/packages."""
        if vector_ids:
            self.index.delete(ids=vector_ids)

    # -----------------------------------------------------------------------
    # Read operations
    # -----------------------------------------------------------------------
    def query(
        self,
        vector: list[float],
        top_k: int = 5,
        filter: dict | None = None,
    ) -> list[dict]:
        """
        Semantic search: return top_k most similar vectors.
        Returns list of {id, score, metadata} dicts.
        """
        result = self.index.query(
            vector          = vector,
            top_k           = top_k,
            include_metadata= True,
            filter          = filter,
        )
        return [
            {
                "id":       match.id,
                "score":    match.score,
                "metadata": match.metadata,
            }
            for match in result.matches
        ]

    def get_total_vectors(self) -> int:
        """Returns the total number of vectors currently in the index."""
        stats = self.index.describe_index_stats()
        return stats.total_vector_count

    def is_healthy(self) -> bool:
        """Used by the health endpoint to check Pinecone connectivity."""
        try:
            self.index.describe_index_stats()
            return True
        except Exception:
            return False