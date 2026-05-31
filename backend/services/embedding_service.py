# from functools import lru_cache
# from sentence_transformers import SentenceTransformer
# from config import get_settings

# settings = get_settings()


# # ---------------------------------------------------------------------------
# # Singleton: model loads once at startup, lives in memory.
# # Calling get_embedding_service() multiple times returns the same object.
# # ---------------------------------------------------------------------------
# @lru_cache(maxsize=1)
# def get_embedding_service() -> "EmbeddingService":
#     return EmbeddingService()


# class EmbeddingService:
#     def __init__(self):
#         print(f"⏳ Loading model: {settings.embedding_model}")
#         self.model = SentenceTransformer(settings.embedding_model)
#         self.dimension = settings.embedding_dimension
#         print(f"✅ Model loaded — dimension: {self.dimension}")

#     def embed(self, text: str) -> list[float]:
#         """Embed a single string. Returns a list of floats (the vector)."""
#         vector = self.model.encode(text, convert_to_numpy=True)
#         return vector.tolist()

#     def embed_batch(self, texts: list[str]) -> list[list[float]]:
#         """
#         Embed multiple strings at once.
#         Batching is faster than calling embed() in a loop because the model
#         can process them in parallel on CPU/GPU.
#         """
#         vectors = self.model.encode(texts, convert_to_numpy=True, batch_size=32)
#         return vectors.tolist()



from functools import lru_cache

# sentence-transformers removed — too heavy for Render free tier (PyTorch ~2GB)
# from sentence_transformers import SentenceTransformer

from fastembed import TextEmbedding
from config import get_settings

settings = get_settings()


@lru_cache(maxsize=1)
def get_embedding_service() -> "EmbeddingService":
    return EmbeddingService()


class EmbeddingService:
    def __init__(self):
        print(f"Loading embedding model: {settings.embedding_model}")

        # fastembed uses same model name, no PyTorch needed
        # old: self.model = SentenceTransformer(settings.embedding_model)
        self.model = TextEmbedding(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        self.dimension = settings.embedding_dimension
        print(f"Embedding model ready — dimension: {self.dimension}")

    def embed(self, text: str) -> list[float]:
        # old: vector = self.model.encode(text, convert_to_numpy=True)
        #      return vector.tolist()
        embeddings = list(self.model.embed([text]))
        return embeddings[0].tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # old: vectors = self.model.encode(texts, convert_to_numpy=True, batch_size=32)
        #      return vectors.tolist()
        embeddings = list(self.model.embed(texts))
        return [e.tolist() for e in embeddings]