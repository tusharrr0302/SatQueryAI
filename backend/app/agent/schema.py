from app.schemas.analysis_request import AnalysisRequest


def _make_strict(schema: dict) -> dict:
    """Make every object property required for Groq strict JSON schemas."""
    if schema.get("type") == "object":
        properties = schema.get("properties", {})
        schema["required"] = list(properties)

        for property_schema in properties.values():
            _make_strict(property_schema)

    for definition in schema.get("$defs", {}).values():
        _make_strict(definition)

    return schema


ANALYSIS_REQUEST_SCHEMA = {
    "name": "analysis_request",
    "strict": True,
    "schema": _make_strict(AnalysisRequest.model_json_schema()),
}