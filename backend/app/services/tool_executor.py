from app.schemas.analysis_request import AnalysisRequest


class ToolExecutor:

    def execute(self, request: AnalysisRequest):
        model = request.model_selection.model

        if model == "geochat-7b":
            return self._run_geochat(request)

        if model == "prithvi-eo-2.0":
            return self._run_prithvi(request)

        if model == "closp":
            return self._run_closp(request)

        if model == "terrafm":
            return self._run_terrafm(request)

        raise ValueError(f"Unsupported model: {model}")

    def _run_geochat(self, request):
        return {
            "model": "geochat-7b",
            "status": "mock",
            "message": "GeoChat tool executed"
        }

    def _run_prithvi(self, request):
        return {
            "model": "prithvi-eo-2.0",
            "status": "mock",
            "message": "Prithvi tool executed"
        }

    def _run_closp(self, request):
        return {
            "model": "closp",
            "status": "mock",
            "message": "CLOSP tool executed"
        }

    def _run_terrafm(self, request):
        return {
            "model": "terrafm",
            "status": "mock",
            "message": "TerraFM tool executed"
        }