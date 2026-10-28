from typing import Dict, List

from app.data_layer.crud.base_crud import BaseCrud
from app.data_layer.data_classes.fire_detection import FireDetection
from app.data_layer.supabase_client import SupabaseClient
from app.data_layer.tables_name_constant import TablesNameConstant


class FireDetectionCrud(BaseCrud):
    """CRUD operations for public.fire_detections."""

    def __init__(self, supabase: SupabaseClient):
        super().__init__(
            supabase=supabase,
            table_name=TablesNameConstant.FIRE_DETECTIONS,
            model_class=FireDetection,
            json_columns={"scores"},
        )

    async def create_detection(
        self,
        image_id: str,
        reading_id: str,
        device_id: str,
        model: str,
        label: str,
        fire_score: float,
        threshold: float,
        fire_detected: bool,
        scores: Dict[str, float],
        inference_ms: int,
    ) -> FireDetection:
        return await self.create(
            {
                "image_id": image_id,
                "reading_id": reading_id,
                "device_id": device_id,
                "model": model,
                "label": label,
                "fire_score": fire_score,
                "threshold": threshold,
                "fire_detected": fire_detected,
                "scores": scores,
                "inference_ms": inference_ms,
            }
        )

    async def get_by_image_ids(self, image_ids: List[str]) -> Dict[str, FireDetection]:
        """image_id -> detection, one query for a whole page of images."""
        if not image_ids:
            return {}
        response = (
            await self.supabase.table(self.table_name)
            .select("*")
            .in_("image_id", image_ids)
            .execute()
        )
        detections = [self._row_to_model(row) for row in response.data]
        return {d.image_id: d for d in detections}
