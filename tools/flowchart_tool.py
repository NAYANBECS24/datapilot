import json
from typing import Any, Dict, List, Optional, Union


def _normalize_schema(schema: Union[str, Dict, None]) -> Optional[Dict]:
    if schema is None:
        return None
    if isinstance(schema, str):
        try:
            schema = json.loads(schema)
        except (json.JSONDecodeError, TypeError):
            return None
    if isinstance(schema, dict):
        if "tables" in schema:
            return schema
        if "schema" in schema and isinstance(schema["schema"], dict):
            return schema["schema"]
    return schema if isinstance(schema, dict) else None


def _er_diagram(schema: Dict[str, Any]) -> str:
    lines = ["erDiagram"]
    tables = schema.get("tables", {})

    for rel in schema.get("relationships", []):
        lines.append(f'    {rel["to_table"]} ||--o{{ {rel["from_table"]} : "via {rel["via"]}"')

    for table_name, meta in tables.items():
        lines.append(f"    {table_name} {{")
        for col in meta["columns"]:
            pk_marker = " PK" if col["primary_key"] else ""
            col_type = col["type"] or "TEXT"
            lines.append(f"        {col_type} {col['name']}{pk_marker}")
        lines.append("    }")

    return "\n".join(lines)


def _process_flow(steps: List[str], decision_points: Optional[Dict[str, List[str]]] = None) -> str:
    lines = ["flowchart TD"]
    node_ids = [f"S{i}" for i in range(len(steps))]

    for nid, label in zip(node_ids, steps):
        safe_label = label.replace('"', "'")
        lines.append(f'    {nid}["{safe_label}"]')

    for i in range(len(node_ids) - 1):
        lines.append(f"    {node_ids[i]} --> {node_ids[i+1]}")

    if decision_points:
        for step_label, branches in decision_points.items():
            if step_label in steps:
                src = node_ids[steps.index(step_label)]
                for b in branches:
                    bid = f"B_{b.replace(' ', '_')}"
                    safe_b = b.replace('"', "'")
                    lines.append(f'    {bid}(["{safe_b}"])')
                    lines.append(f"    {src} -. branch .-> {bid}")

    return "\n".join(lines)


def _decision_tree(question: str, branches: List[Dict[str, Any]]) -> str:
    lines = ["flowchart TD"]
    qid = "Q0"
    safe_q = question.replace('"', "'").replace("\n", " ")
    lines.append(f'    {qid}["{safe_q}"]')

    node_counter = 1

    def add_branch(parent_id, label, children, depth=0):
        nonlocal node_counter
        nid = f"N{node_counter}"
        node_counter += 1
        safe_label = label.replace('"', "'").replace("\n", " ")
        if children:
            lines.append(f'    {nid}{{"{safe_label}"}}')
            lines.append(f'    {parent_id} -->|{safe_label}| {nid}')
            for child in children:
                add_branch(nid, child.get("label", ""), child.get("children", []), depth + 1)
        else:
            lines.append(f'    {nid}["{safe_label}"]')
            lines.append(f'    {parent_id} -->|{safe_label}| {nid}')
            lines.append(f'    style {nid} fill:#00d4aa20,stroke:#00d4aa,stroke-width:1px')

    for branch in branches:
        add_branch(qid, branch.get("label", ""), branch.get("children", []))

    return "\n".join(lines)


def generate_flowchart(
    diagram_type: str,
    schema: Optional[Union[str, Dict[str, Any]]] = None,
    steps: Optional[List[str]] = None,
    decision_points: Optional[Dict[str, List[str]]] = None,
    question: Optional[str] = None,
    branches: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    try:
        if diagram_type == "er_diagram":
            schema = _normalize_schema(schema)
            if not schema:
                return {
                    "success": False,
                    "error": "A valid schema dict is required for er_diagram. Call get_schema first and pass its result (or the nested 'schema' key).",
                }
            code = _er_diagram(schema)
        elif diagram_type == "decision_tree":
            if not question or not branches:
                return {"success": False, "error": "question and branches are required for decision_tree."}
            code = _decision_tree(question, branches)
        elif diagram_type == "process_flow":
            if not steps:
                return {"success": False, "error": "steps list is required for process_flow."}
            code = _process_flow(steps, decision_points)
        else:
            return {"success": False, "error": "diagram_type must be 'er_diagram', 'decision_tree', or 'process_flow'."}

        return {"success": True, "diagram_type": diagram_type, "mermaid_code": code}

    except Exception as e:
        return {"success": False, "error": f"Flowchart generation failed: {e}"}


if __name__ == "__main__":
    import json, os, sys
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from tools.schema_tool import get_schema

    db_path = os.path.join(os.path.dirname(__file__), "..", "db", "sample_ecommerce.db")
    schema_result = get_schema(db_path)

    print("== ER DIAGRAM ==")
    er = generate_flowchart("er_diagram", schema=schema_result["schema"])
    print(er.get("mermaid_code", er.get("error")))

    print("\n== PROCESS FLOW ==")
    pf = generate_flowchart(
        "process_flow",
        steps=["Order Placed", "Confirmed", "Shipped", "Delivered"],
        decision_points={"Confirmed": ["Cancelled"]},
    )
    print(pf.get("mermaid_code", pf.get("error")))
