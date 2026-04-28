from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_url: str = "postgresql://sb:sbpass@localhost:5432/sbdb"
    secret_key: str = "your-secret-key-change-in-production-use-env-var"
    openai_api_key: str = ""
    
    class Config:
        env_file = ".env"

settings = Settings()
