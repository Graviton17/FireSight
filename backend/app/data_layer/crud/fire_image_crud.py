from typing import Dict, List, Tuple

from app.data_layer.crud.base_crud import BaseCrud
from app.data_layer.data_classes.fire_image import FireImage
from app.data_layer.supabase_client import SupabaseClient
from app.data_layer.tables_name_constant import TablesNameConstant


class FireImageCrud(BaseCrud):
    """CRUD operations for public.fire_images."""

    def __init__(self, supabase: SupabaseClient):
        super().__init__(
            supabase=supabase,
            table_name=TablesNameConstant.FIRE_IMAGES,
            model_class=FireImage,
        )

    async def create_image(
        self,
        reading_id: str,
        device_id: str,
        bucket: str,
        storage_path: str,
        content_type: str,
        size_bytes: int,
        captured_at: str,
    ) -> FireImage:
        return await self.create(
            {
                "reading_id": reading_id,
                "device_id": device_id,
                "bucket": bucket,
                "storage_path": storage_path,
                "content_type": content_type,
                "size_bytes": size_bytes,
                "captured_at": captured_at,
            }
        )

    async def get_by_reading_ids(self, reading_ids: List[str]) -> Dict[str, FireImage]:
        """reading_id -> image, one query for a whole page of readings."""
        if not reading_ids:
            return {}
        response = (
            await self.supabase.table(self.table_name)
            .select("*")
            .in_("reading_id", reading_ids)
            .execute()
        )
        images = [self._row_to_model(row) for row in response.data]
        return {image.reading_id: image for image in images}

    async def list_for_device(
        self,
        device_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[FireImage], int]:
        """Newest first."""
        return await self.paginate(
            page=page,
            page_size=page_size,
            order_by="captured_at",
            descending=True,
            device_id=device_id,
        )
