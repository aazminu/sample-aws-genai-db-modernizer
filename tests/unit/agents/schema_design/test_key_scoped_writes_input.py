"""The DynamoDB designer is given each key-scoped write's key requirement (#1061).

#1038 records, for a write that changes the rows one value of a key anchor addresses,
that the column must become a partition key (or a GSI's) so the write reads its items
by key. It lived only in the decision trace, which the DynamoDB designer never reads.
The DynamoDB analysis now carries it in its contract (``key_scoped_writes``), from the
same ``transaction_shape`` the trace reads, so every designer input path has it: the
external request (``prepare_schema_design_input``), the Bedrock projection
(``load_agent_input``) and each design group's input (``build_group_input``), which
keeps the group's own writes only. No test calls a model.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from src.agents.analysis.dynamodb_analysis_agent import analyze_for_dynamodb_deterministic
from src.agents.schema_design.group_input import build_group_input
from src.agents.schema_design.handler import prepare_schema_design_input
from src.contracts.analysis_input import AnalysisInput, TargetDatabase
from src.contracts.analysis_output import AnalysisOutputContract
from src.storage.local_store import LocalArtifactStore
from src.tools.schema.base_schema_agent import AgentInputPaths
from src.tools.schema.dynamodb_schema_agent import load_agent_input
from tests.fixtures.ecommerce_collector_output import get_ecommerce_collector_output

DB, JOB = "ecommerce", "job-1061"
NOTE = (
    "order_items.order_id must become the partition key of an item collection "
    "(or a GSI's) so this write reads its items by key"
)


def _write(qid: str, text: str, table: str) -> dict:
    return {
        "query_id": qid,
        "query_text": text,
        "query_type": "DELETE",
        "frequency_per_hour": 60.0,
        "calls_per_second": 0.0167,
        "tables_accessed": [f"ecommerce.{table}"],
    }


# By ``order_id``, a foreign key that is not unique: key scoped.
BY_ORDER = _write("w-items-by-order", "DELETE FROM order_items WHERE order_id = ?", "order_items")
# By the primary key: one item, no requirement.
BY_PK = _write("w-item-by-pk", "DELETE FROM order_items WHERE item_id = ?", "order_items")


def _collector() -> dict:
    collector = copy.deepcopy(get_ecommerce_collector_output())
    collector["queries"]["query_patterns"] += [BY_ORDER, BY_PK]
    return collector


def _analysis(collector: dict) -> tuple[dict, dict]:
    contract, trace, _ = analyze_for_dynamodb_deterministic(
        AnalysisInput(
            job_id=JOB, collector_output=collector, target_database=TargetDatabase.DYNAMODB
        )
    )
    return contract.model_dump(mode="json"), trace


def test_the_analysis_carries_each_key_scoped_write_and_the_key_it_needs() -> None:
    analysis, _ = _analysis(_collector())
    assert analysis["contract_version"] == "2.2"
    assert analysis["key_scoped_writes"] == [
        {
            "query_id": "w-items-by-order",
            "table_id": "ecommerce.order_items",
            "columns": ["order_id"],
            "schema_note": NOTE,
        }
    ]


def test_it_is_exactly_what_the_decision_trace_records() -> None:
    analysis, trace = _analysis(_collector())
    noted = {
        m["query_id"]: m["transaction_shape"]["schema_note"]
        for m in trace["query_matches"]
        if (m.get("transaction_shape") or {}).get("schema_note")
    }
    assert {w["query_id"]: w["schema_note"] for w in analysis["key_scoped_writes"]} == noted


def test_no_key_scoped_write_writes_no_field() -> None:
    analysis, _ = _analysis(get_ecommerce_collector_output())
    assert analysis.get("key_scoped_writes") is None


def test_a_saved_2_1_analysis_still_loads() -> None:
    analysis, _ = _analysis(get_ecommerce_collector_output())
    old = {k: v for k, v in analysis.items() if k != "key_scoped_writes"}
    old["contract_version"] = "2.1"
    assert AnalysisOutputContract.model_validate(old).key_scoped_writes is None


def _store(tmp_path: Path, collector: dict, analysis: dict) -> LocalArtifactStore:
    store = LocalArtifactStore(base_dir=str(tmp_path))
    store.write_json(f"{DB}/{JOB}/collector/output.json", collector)
    store.write_json(f"{DB}/{JOB}/analysis-dynamodb/analysis.json", analysis)
    return store


def _bedrock_input(tmp_path: Path, collector: dict, analysis: dict) -> dict:
    paths = []
    for name, data in (("collector", collector), ("analysis", analysis)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(data, default=str))
        paths.append(str(path))
    return load_agent_input(AgentInputPaths(collector=paths[0], analysis=paths[1]))


def test_the_external_request_and_the_bedrock_projection_carry_the_same_list(tmp_path) -> None:
    collector = _collector()
    analysis, _ = _analysis(collector)
    external = prepare_schema_design_input(
        JOB, DB, "dynamodb", _store(tmp_path, collector, analysis)
    )
    bedrock = _bedrock_input(tmp_path, collector, analysis)
    assert external["analysis_output"]["key_scoped_writes"] == analysis["key_scoped_writes"]
    assert bedrock["analysis"]["key_scoped_writes"] == analysis["key_scoped_writes"]


def _group(collector: dict, analysis: dict, query_ids: set[str]) -> dict:
    queries = [q for q in collector["queries"]["query_patterns"] if q["query_id"] in query_ids]
    tables = [
        t
        for t in collector["database_schema"]["tables"]
        if any(t["table_id"] in q["tables_accessed"] for q in queries)
    ]
    return build_group_input(
        job_id=JOB,
        database_name=DB,
        engine="dynamodb",
        group_index=0,
        group_name="g",
        primary_tables=[t["table_id"] for t in tables],
        group_queries=queries,
        group_tables=tables,
        collector_output=collector,
        analysis_output=analysis,
        total_queries=len(collector["queries"]["query_patterns"]),
    )


def test_a_design_group_keeps_its_own_key_scoped_writes_only(tmp_path) -> None:
    collector = _collector()
    analysis, _ = _analysis(collector)
    mine = _group(collector, analysis, {"w-items-by-order", "w-item-by-pk"})
    assert mine["analysis_output"]["key_scoped_writes"] == analysis["key_scoped_writes"]
    other = _group(collector, analysis, {"w-item-by-pk"})
    assert "key_scoped_writes" not in other["analysis_output"]
    # The Bedrock path validates and projects the group's own files: the same list.
    bedrock = _bedrock_input(tmp_path, mine["collector_output"], mine["analysis_output"])
    assert bedrock["analysis"]["key_scoped_writes"] == analysis["key_scoped_writes"]
