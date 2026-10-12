"""Persistence layer: one repository interface, in-memory and DynamoDB/S3 backends."""

from chronosmesh.config import Settings, get_settings
from chronosmesh.persistence.base import Repository
from chronosmesh.persistence.memory import MemoryRepository


def create_repository(settings: Settings = None) -> Repository:
    """Pick the backend from configuration (AWS when tables/bucket are configured, else memory)."""
    settings = settings or get_settings()
    if settings.use_aws_storage:
        from chronosmesh.persistence.aws import AwsRepository

        return AwsRepository(settings)
    return MemoryRepository()


__all__ = ["Repository", "MemoryRepository", "create_repository"]
