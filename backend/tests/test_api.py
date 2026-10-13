"""
API integration tests.

Tests:
- GET /health
- POST /experiments/import (XLSX and XML)
- GET /experiments
- GET /experiments/{id}
- GET /experiments/{id}/evaluation
- Duplicate import detection
- Invalid file type rejection
"""

import io
import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_xlsx_bytes, make_xml_bytes


class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_responds_quickly(self, client: TestClient):
        """Health endpoint must be fast — no DB queries."""
        import time
        start = time.time()
        client.get("/health")
        elapsed = time.time() - start
        assert elapsed < 1.0


class TestImportEndpoint:
    def test_import_xlsx_success(self, client: TestClient):
        content = make_xlsx_bytes(num_rows=10)
        response = client.post(
            "/experiments/import",
            files={"file": ("test_report.xlsx", io.BytesIO(content),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["imported"] is True
        assert data["source_format"] == "xlsx"
        assert data["experiments_created"] == 10
        assert data["import_batch_id"] is not None

    def test_import_xml_success(self, client: TestClient):
        content = make_xml_bytes(num_rows=8)
        response = client.post(
            "/experiments/import",
            files={"file": ("ReportOptimizer-123.xml", io.BytesIO(content), "application/xml")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["imported"] is True
        assert data["source_format"] == "xml"
        assert data["experiments_created"] == 8

    def test_import_counts_sum_to_total(self, client: TestClient):
        content = make_xlsx_bytes(num_rows=20)
        response = client.post(
            "/experiments/import",
            files={"file": ("test.xlsx", io.BytesIO(content),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        data = response.json()
        total_classified = data["qualified"] + data["rejected"] + data["insufficient_data"] + data["pending"]
        assert total_classified == data["experiments_created"]

    def test_import_warns_about_missing_win_rate(self, client: TestClient):
        content = make_xlsx_bytes(num_rows=5, include_win_rate=False)
        response = client.post(
            "/experiments/import",
            files={"file": ("test.xlsx", io.BytesIO(content),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        data = response.json()
        warnings_text = " ".join(data.get("warnings", [])).lower()
        assert "win rate" in warnings_text

    def test_import_duplicate_detected(self, client: TestClient):
        content = make_xlsx_bytes(num_rows=5)
        file_tuple = ("dup_test.xlsx", io.BytesIO(content),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # First import
        client.post("/experiments/import", files={"file": file_tuple})

        # Second import — same content
        response = client.post(
            "/experiments/import",
            files={"file": ("dup_test.xlsx", io.BytesIO(content),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["imported"] is False
        assert data["duplicate"] is True

    def test_import_unsupported_type_rejected(self, client: TestClient):
        response = client.post(
            "/experiments/import",
            files={"file": ("report.csv", io.BytesIO(b"a,b,c\n1,2,3"), "text/csv")},
        )
        assert response.status_code == 415

    def test_import_empty_file_rejected(self, client: TestClient):
        response = client.post(
            "/experiments/import",
            files={"file": ("empty.xlsx", io.BytesIO(b""),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert response.status_code == 400

    def test_import_invalid_xlsx_rejected(self, client: TestClient):
        response = client.post(
            "/experiments/import",
            files={"file": ("bad.xlsx", io.BytesIO(b"THIS IS NOT XLSX"),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert response.status_code == 422

    def test_import_source_hash_returned(self, client: TestClient):
        content = make_xlsx_bytes(num_rows=3)
        response = client.post(
            "/experiments/import",
            files={"file": ("test.xlsx", io.BytesIO(content),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        data = response.json()
        assert len(data["source_hash"]) == 64  # SHA-256 hex


class TestListExperimentsEndpoint:
    def _import_xlsx(self, client, num_rows=10, include_win_rate=False):
        content = make_xlsx_bytes(num_rows=num_rows, include_win_rate=include_win_rate)
        client.post(
            "/experiments/import",
            files={"file": (f"test_{num_rows}.xlsx", io.BytesIO(content),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )

    def test_list_returns_paginated_response(self, client: TestClient):
        self._import_xlsx(client, num_rows=15)
        response = client.get("/experiments?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "items" in data
        assert len(data["items"]) <= 10

    def test_list_total_matches_created(self, client: TestClient):
        self._import_xlsx(client, num_rows=20)
        response = client.get("/experiments?page_size=5")
        data = response.json()
        assert data["total"] == 20
        assert len(data["items"]) == 5

    def test_list_filter_by_symbol(self, client: TestClient):
        self._import_xlsx(client, num_rows=5)
        response = client.get("/experiments?symbol=EURUSD")
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["symbol"] == "EURUSD"

    def test_list_filter_by_evaluation_status(self, client: TestClient):
        self._import_xlsx(client, num_rows=20)
        response = client.get("/experiments?evaluation_status=INSUFFICIENT_DATA")
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["evaluation_status"] == "INSUFFICIENT_DATA"

    def test_list_filter_invalid_status_rejected(self, client: TestClient):
        response = client.get("/experiments?evaluation_status=INVALID_VALUE")
        assert response.status_code == 400

    def test_list_pagination_second_page(self, client: TestClient):
        self._import_xlsx(client, num_rows=15)
        r1 = client.get("/experiments?page=1&page_size=10").json()
        r2 = client.get("/experiments?page=2&page_size=10").json()
        ids_page1 = {item["id"] for item in r1["items"]}
        ids_page2 = {item["id"] for item in r2["items"]}
        assert len(ids_page2) == 5
        assert ids_page1.isdisjoint(ids_page2)

    def test_list_empty_database_returns_zero(self, client: TestClient):
        response = client.get("/experiments")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []


class TestExperimentDetailEndpoint:
    def _import_and_get_first_id(self, client):
        content = make_xlsx_bytes(num_rows=3)
        client.post(
            "/experiments/import",
            files={"file": ("test.xlsx", io.BytesIO(content),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        items = client.get("/experiments").json()["items"]
        return items[0]["id"]

    def test_detail_returns_200(self, client: TestClient):
        exp_id = self._import_and_get_first_id(client)
        response = client.get(f"/experiments/{exp_id}")
        assert response.status_code == 200

    def test_detail_contains_parameters(self, client: TestClient):
        exp_id = self._import_and_get_first_id(client)
        data = client.get(f"/experiments/{exp_id}").json()
        assert "parameters" in data
        assert len(data["parameters"]) > 0

    def test_detail_contains_metrics(self, client: TestClient):
        exp_id = self._import_and_get_first_id(client)
        data = client.get(f"/experiments/{exp_id}").json()
        assert "metrics" in data
        assert len(data["metrics"]) > 0

    def test_detail_contains_metadata(self, client: TestClient):
        exp_id = self._import_and_get_first_id(client)
        data = client.get(f"/experiments/{exp_id}").json()
        assert data["symbol"] == "EURUSD"
        assert data["timeframe"] == "H1"

    def test_detail_not_found_returns_404(self, client: TestClient):
        response = client.get("/experiments/999999")
        assert response.status_code == 404


class TestEvaluationEndpoint:
    def _import_xlsx_and_get_first_id(self, client, include_win_rate=False):
        content = make_xlsx_bytes(num_rows=5, include_win_rate=include_win_rate)
        client.post(
            "/experiments/import",
            files={"file": ("test.xlsx", io.BytesIO(content),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        items = client.get("/experiments").json()["items"]
        return items[0]["id"]

    def test_evaluation_returns_200(self, client: TestClient):
        exp_id = self._import_xlsx_and_get_first_id(client)
        response = client.get(f"/experiments/{exp_id}/evaluation")
        assert response.status_code == 200

    def test_evaluation_has_overall_status(self, client: TestClient):
        exp_id = self._import_xlsx_and_get_first_id(client)
        data = client.get(f"/experiments/{exp_id}/evaluation").json()
        assert "overall_status" in data
        assert data["overall_status"] in ("QUALIFIED", "REJECTED", "INSUFFICIENT_DATA")

    def test_evaluation_has_three_rules(self, client: TestClient):
        exp_id = self._import_xlsx_and_get_first_id(client)
        data = client.get(f"/experiments/{exp_id}/evaluation").json()
        assert len(data["rules"]) == 3

    def test_evaluation_rule_structure(self, client: TestClient):
        exp_id = self._import_xlsx_and_get_first_id(client)
        data = client.get(f"/experiments/{exp_id}/evaluation").json()
        for rule in data["rules"]:
            assert "metric" in rule
            assert "operator" in rule
            assert "threshold" in rule
            assert "actual_value" in rule
            assert "status" in rule
            assert rule["status"] in ("PASS", "FAIL", "INSUFFICIENT_DATA")

    def test_evaluation_win_rate_insufficient_when_absent(self, client: TestClient):
        exp_id = self._import_xlsx_and_get_first_id(client, include_win_rate=False)
        data = client.get(f"/experiments/{exp_id}/evaluation").json()
        wr_rule = next(r for r in data["rules"] if r["metric"] == "win_rate")
        assert wr_rule["status"] == "INSUFFICIENT_DATA"
        assert wr_rule["actual_value"] is None

    def test_evaluation_not_found_returns_404(self, client: TestClient):
        response = client.get("/experiments/999999/evaluation")
        assert response.status_code == 404

    def test_evaluation_experiment_id_matches(self, client: TestClient):
        exp_id = self._import_xlsx_and_get_first_id(client)
        data = client.get(f"/experiments/{exp_id}/evaluation").json()
        assert data["experiment_id"] == exp_id
