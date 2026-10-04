from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    supabase_jwt_secret: str
    supabase_url: str
    # Models -- section 9 of the design doc: chat and utility are separate
    chat_model: str = "openai/gpt-4o-mini"
    utility_model: str = "openai/gpt-4o-mini"
    embedding_model: str = "openai/text-embedding-3-small"
    embedding_dim: int = 1536
    typesafe_api_base: str = "https://api.typesafe.ai"
    jev_model: str = "jev-latest"

    # Chunking -- section 6, step 3
    chunk_max_tokens: int = 700
    chunk_overlap_tokens: int = 100
    chunk_min_tokens: int = 80

    # Retrieval -- section 7
    retrieve_candidates: int = 30
    # Narrow questions don't need the full pool; broad ones (lists,
    # overviews) keep retrieve_candidates. See understand.StructuredQuery.
    retrieve_candidates_narrow: int = 16
    retrieve_final: int = 8
    # How many earlier questions in the conversation understand() gets as context.
    previous_questions_limit: int = 5

    temperature: float = 0.1


settings = Settings()