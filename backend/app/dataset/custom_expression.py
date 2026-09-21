"""
SatQuery AI — Custom Expression Validator
AST-based safe validator for user-defined band composites and raster index formulas.
Strictly disallows eval() and arbitrary code execution.
"""
import ast
from typing import Any, Dict, List, Optional, Set, Tuple

from app.schemas.data_catalog import CustomVisualizationSpec, LayerDefinition
from app.dataset.registry import get_dataset


# Allowed AST node types for safe mathematical expressions
ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Name,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.USub,
    ast.UAdd,
    ast.Load,
)

# Standard band aliases that can map to sensor bands
BAND_ALIASES: Dict[str, List[str]] = {
    "NIR": ["B08", "B8A", "B8", "B5", "NIR"],
    "RED": ["B04", "B4", "RED"],
    "GREEN": ["B03", "B3", "GREEN"],
    "BLUE": ["B02", "B2", "BLUE"],
    "SWIR1": ["B11", "B6", "SWIR1"],
    "SWIR2": ["B12", "B7", "SWIR2"],
    "RED_EDGE": ["B05", "B06", "B07", "B5", "B6", "B7"],
}

SUPPORTED_COLOR_MAPS = {
    "viridis",
    "plasma",
    "inferno",
    "magma",
    "cividis",
    "rdylgn",
    "turbo",
    "spectral",
    "coolwarm",
    "blues",
    "greens",
    "reds",
}


class CustomExpressionValidationError(ValueError):
    """Raised when a custom visualization spec fails AST or domain validation."""
    pass


class SafeFormulaVisitor(ast.NodeVisitor):
    """
    AST visitor that traverses an expression and verifies that every node
    is in ALLOWED_AST_NODES. Collects variable (band) names.
    """

    def __init__(self):
        self.variables: Set[str] = set()
        self.is_valid = True
        self.errors: List[str] = []

    def generic_visit(self, node: ast.AST):
        if not isinstance(node, ALLOWED_AST_NODES):
            self.is_valid = False
            self.errors.append(
                f"Disallowed syntax element '{type(node).__name__}'. Only basic arithmetic (+, -, *, /) is permitted."
            )
            return
        super().generic_visit(node)

    def visit_Name(self, node: ast.Name):
        self.variables.add(node.id)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        self.is_valid = False
        self.errors.append("Function calls are strictly forbidden in custom formulas.")

    def visit_Attribute(self, node: ast.Attribute):
        self.is_valid = False
        self.errors.append("Attribute access is strictly forbidden in custom formulas.")

    def visit_Subscript(self, node: ast.Subscript):
        self.is_valid = False
        self.errors.append("Subscript indexing is strictly forbidden in custom formulas.")


def validate_formula_ast(formula: str) -> Tuple[bool, Set[str], List[str]]:
    """
    Parse a formula string using ast.parse in 'eval' mode and validate safety.
    Returns: (is_valid, variable_names, error_messages)
    """
    if not formula or not formula.strip():
        return False, set(), ["Formula expression cannot be empty."]

    cleaned_formula = formula.strip()
    if len(cleaned_formula) > 250:
        return False, set(), ["Formula exceeds maximum length of 250 characters."]

    try:
        parsed = ast.parse(cleaned_formula, mode="eval")
    except SyntaxError as e:
        return False, set(), [f"Syntax error in formula: {e.msg} at line {e.lineno}, col {e.offset}"]

    visitor = SafeFormulaVisitor()
    visitor.visit(parsed)

    if not visitor.is_valid:
        return False, visitor.variables, visitor.errors

    if not visitor.variables:
        return False, set(), ["Formula must reference at least one satellite band."]

    return True, visitor.variables, []


def validate_custom_visualization_spec(
    spec: CustomVisualizationSpec,
    dataset_id: str,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Validates a CustomVisualizationSpec against the target dataset metadata.
    Returns (is_valid, errors, normalized_metadata).
    """
    errors: List[str] = []
    dataset = get_dataset(dataset_id)
    if not dataset:
        return False, [f"Target dataset '{dataset_id}' not found in registry."], {}

    available_bands = {b.upper() for b in dataset.bands}

    if spec.type == "band_composite":
        if not spec.bands:
            return False, ["'bands' mapping (e.g. r, g, b) is required for band_composite."], {}

        normalized_bands: Dict[str, str] = {}
        for channel, band_name in spec.bands.items():
            ch_lower = channel.lower()
            if ch_lower in ("r", "red"):
                target_ch = "r"
            elif ch_lower in ("g", "green"):
                target_ch = "g"
            elif ch_lower in ("b", "blue"):
                target_ch = "b"
            else:
                errors.append(f"Invalid composite channel '{channel}'. Allowed: 'r'/'red', 'g'/'green', 'b'/'blue'.")
                continue

            b_upper = band_name.strip().upper()
            # If dataset has bands defined, verify
            if available_bands and b_upper not in available_bands:
                # Check alias mapping
                matched = False
                for alias, band_list in BAND_ALIASES.items():
                    if b_upper == alias or b_upper in band_list:
                        for cand in band_list:
                            if cand in available_bands:
                                b_upper = cand
                                matched = True
                                break
                    if matched:
                        break
                if not matched and available_bands:
                    errors.append(f"Band '{band_name}' is not available in dataset '{dataset_id}'. Available: {sorted(list(available_bands))}")

            normalized_bands[target_ch] = b_upper

        if "r" not in normalized_bands or "g" not in normalized_bands or "b" not in normalized_bands:
            errors.append("RGB band composite must specify red ('r'), green ('g'), and blue ('b') channels.")

        if errors:
            return False, errors, {}

        return True, [], {
            "type": "band_composite",
            "bands": normalized_bands,
            "dataset_id": dataset_id,
            "display_name": f"Custom Composite ({normalized_bands.get('r')}-{normalized_bands.get('g')}-{normalized_bands.get('b')})",
        }

    elif spec.type == "index":
        if not spec.formula:
            return False, ["'formula' string is required for index visualization."], {}

        is_ast_valid, vars_found, ast_errors = validate_formula_ast(spec.formula)
        if not is_ast_valid:
            return False, ast_errors, {}

        # Validate that variables exist in dataset bands or aliases
        resolved_bands: Dict[str, str] = {}
        for var in vars_found:
            v_upper = var.upper()
            if available_bands and v_upper not in available_bands:
                matched = False
                for alias, band_list in BAND_ALIASES.items():
                    if v_upper == alias or v_upper in band_list:
                        for cand in band_list:
                            if cand in available_bands:
                                resolved_bands[var] = cand
                                matched = True
                                break
                    if matched:
                        break
                if not matched and available_bands:
                    errors.append(f"Variable '{var}' does not correspond to any band in dataset '{dataset_id}'. Available: {sorted(list(available_bands))}")
            else:
                resolved_bands[var] = v_upper

        # Validate output_range
        output_range = spec.output_range or [-1.0, 1.0]
        if not (isinstance(output_range, (list, tuple)) and len(output_range) == 2 and output_range[0] < output_range[1]):
            errors.append("output_range must be a 2-element list [min, max] where min < max.")

        # Validate color_map
        color_map = (spec.color_map or "viridis").lower()
        if color_map not in SUPPORTED_COLOR_MAPS:
            errors.append(f"Color map '{color_map}' is not supported. Supported: {sorted(list(SUPPORTED_COLOR_MAPS))}")

        if errors:
            return False, errors, {}

        return True, [], {
            "type": "index",
            "formula": spec.formula,
            "resolved_bands": resolved_bands,
            "output_range": output_range,
            "color_map": color_map,
            "dataset_id": dataset_id,
            "display_name": f"Custom Index ({spec.formula})",
        }

    else:
        return False, [f"Unsupported visualization type '{spec.type}'. Must be 'band_composite' or 'index'."], {}


def create_custom_layer_definition(
    spec: CustomVisualizationSpec,
    dataset_id: str,
    layer_name: Optional[str] = None,
) -> LayerDefinition:
    """
    Validates spec and converts it into a valid LayerDefinition ready to be registered in LayerCatalog.
    Raises CustomExpressionValidationError if validation fails.
    """
    is_valid, errors, meta = validate_custom_visualization_spec(spec, dataset_id)
    if not is_valid:
        raise CustomExpressionValidationError("; ".join(errors))

    name = layer_name or meta.get("display_name", "Custom Visualization Layer")
    clean_slug = "".join(c if c.isalnum() else "_" for c in name.lower())[:30].strip("_")
    layer_id = f"{dataset_id}-custom-{clean_slug}"

    if spec.type == "band_composite":
        required_bands = list(meta["bands"].values())
        return LayerDefinition(
            layer_id=layer_id,
            dataset_id=dataset_id,
            name=name,
            category="custom_composite",
            visualization_type="rgb_composite",
            required_bands=required_bands,
            units="reflectance",
            temporal=True,
            spatial=True,
            supports_cesium=True,
            supports_analysis=True,
            legend={"channels": meta["bands"]},
            description=f"User-defined band composite ({meta['bands'].get('r')}, {meta['bands'].get('g')}, {meta['bands'].get('b')}) for {dataset_id}.",
            limitations="Requires valid scenes with all specified bands present.",
            custom_expression=meta,
            role="primary_analysis",
        )
    else:
        required_bands = list(meta["resolved_bands"].values())
        return LayerDefinition(
            layer_id=layer_id,
            dataset_id=dataset_id,
            name=name,
            category="custom_index",
            visualization_type="single_band_index",
            required_bands=required_bands,
            units="index_ratio",
            temporal=True,
            spatial=True,
            supports_cesium=True,
            supports_analysis=True,
            legend={
                "min": meta["output_range"][0],
                "max": meta["output_range"][1],
                "colormap": meta["color_map"],
                "formula": meta["formula"],
            },
            description=f"User-defined arithmetic index ({meta['formula']}) with {meta['color_map']} colormap.",
            limitations="Formula assumes normalized reflectance bands.",
            custom_expression=meta,
            role="primary_analysis",
        )
