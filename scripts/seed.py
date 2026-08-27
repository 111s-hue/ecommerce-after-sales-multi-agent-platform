from app.config import get_settings
from app.infrastructure.repository import SQLAlchemySupportRepository
from app.services.identity import IdentityService


def main() -> None:
    settings = get_settings()
    repository = SQLAlchemySupportRepository(settings.database_url)
    repository.init_schema()
    if settings.seed_demo_data:
        repository.seed_demo_data()
        IdentityService(repository.engine).seed_development_identities()
        print("Demo data and development identities are ready")
    else:
        print("SEED_DEMO_DATA is disabled; no demonstration records were created")


if __name__ == "__main__":
    main()
