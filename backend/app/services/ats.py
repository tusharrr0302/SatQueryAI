from app.schemas.analysis_request import AnalysisRequest
from app.services.request_validator import RequestValidator
from app.services.tool_executor import ToolExecutor


class AgenticToolSystem:

    def __init__(self):
        self.validator = RequestValidator()
        self.executor = ToolExecutor()

    def run(self, request: AnalysisRequest):

        # 1. Validate LLM-generated request
        self.validator.validate(request)

        # 2. Execute the selected tool/model
        result = self.executor.execute(request)

        return {
            "request": request.model_dump(),
            "result": result
        }