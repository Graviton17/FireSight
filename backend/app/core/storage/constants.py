"""Storage bucket ids and upload limits."""


class StorageBuckets:
    FIRE_IMAGES = "fire-images"


class FireImageLimits:
    MAX_BYTES = 5 * 1024 * 1024  # 5 MiB, matches the bucket's file_size_limit
    CONTENT_TYPE = "image/jpeg"
    # Signed URLs handed to the frontend
    SIGNED_URL_TTL_SECONDS = 60 * 60
