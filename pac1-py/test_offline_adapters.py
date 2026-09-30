"""Offline adapter contract checks; no benchmark or model calls."""
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from agent_evolve.types import Task, Trajectory
from bitgn_agent import BitgnAgent
from bitgn_benchmark import BitgnBenchmarkAdapter
from domain_ecom import (
    EcomDomain, NextStep, Req_Read, Req_Search, Req_Write, Req_Delete,
    Req_Stat, Req_Exec, Req_Find, Req_Tree, Req_List, ReportTaskCompletion,
)
from domain_protocol import DomainProtocol


class OfflineAdapterTests(unittest.TestCase):
    def test_filesystem_remains_default_even_for_ecom_benchmark(self):
        with patch.dict(os.environ, {"BITGN_DOMAIN": "", "BENCHMARK_ID": "bitgn/ecom1"}):
            import agent
            self.assertEqual(agent._select_domain().name, "filesystem")
        with patch.dict(os.environ, {"BITGN_DOMAIN": "ecom"}):
            self.assertIsInstance(agent._select_domain(), EcomDomain)
        with patch.dict(os.environ, {"BITGN_DOMAIN": "typo"}):
            with self.assertRaises(ValueError):
                agent._select_domain()

    def test_ecom_requests_match_generated_sdk(self):
        domain = EcomDomain()
        self.assertIsInstance(domain, DomainProtocol)
        cases = [
            (Req_Tree(tool="tree", root="/catalog", level=3), "tree", {"root": "/catalog", "level": 3}),
            (Req_Find(tool="find", name="item", root="/catalog", kind="files", limit=2), "find", {"name":"item", "limit":2}),
            (Req_List(tool="list", path="/catalog"), "list", {"path":"/catalog"}),
            (Req_Read(tool="read", path="/catalog/a", start_line=2, end_line=4), "read", {"path":"/catalog/a", "start_line":2, "end_line":4}),
            (Req_Search(tool="search", query="red", path="/catalog", limit=7), "search", {"root":"/catalog", "pattern":"red", "limit":7}),
            (Req_Write(tool="write", path="/out/a", content="x"), "write", {"path":"/out/a", "content":"x"}),
            (Req_Delete(tool="delete", path="/out/a"), "delete", {"path":"/out/a"}),
            (Req_Stat(tool="stat", path="/catalog"), "stat", {"path":"/catalog"}),
            (Req_Exec(tool="exec", path="/bin/sql", args=["--read"], stdin="SELECT 1"), "exec", {"path":"/bin/sql", "stdin":"SELECT 1"}),
            (ReportTaskCompletion(tool="report_completion", completed_steps_laconic=["read"], message="done", outcome="OUTCOME_OK", grounding_refs=["/catalog/a"]), "answer", {"message":"done", "refs":["/catalog/a"]}),
        ]
        for command, method, fields in cases:
            with self.subTest(method=method):
                client=Mock()
                domain.dispatch(client, command)
                req=getattr(client,method).call_args.args[0]
                for key,value in fields.items():
                    actual=getattr(req,key)
                    self.assertEqual(list(actual) if isinstance(value,list) else actual,value)
                parsed=NextStep.model_validate({"current_state":"fixture", "plan_remaining_steps_brief":["next"], "task_completed":method=="answer", "function":command.model_dump()})
                self.assertIs(type(parsed.function),type(command))
        with self.assertRaises(ValueError):
            domain.dispatch(Mock(), SimpleNamespace(tool="unknown"))

    def test_truncation_and_exec_errors_remain_visible(self):
        d=EcomDomain()
        text=d.format_result(Req_Read(tool="read",path="/x"),SimpleNamespace(content="partial",truncated=True))
        self.assertIn("TRUNCATED",text)
        text=d.format_result(Req_Exec(tool="exec",path="/bin/sql"),SimpleNamespace(stdout="",stderr="syntax error",exit_code=2))
        self.assertIn("syntax error",text)
        self.assertIn("[exit 2]",text)

    def test_solve_preserves_score_and_exports_real_metrics(self):
        obj=BitgnAgent.__new__(BitgnAgent)
        obj._benchmark_id="offline"
        obj._model="unused"
        obj._harness_client=Mock()
        obj._harness_client.start_playground.return_value=SimpleNamespace(harness_url="offline",instruction="fixture task",trial_id="trial")
        obj._harness_client.end_trial.return_value=SimpleNamespace(score=1.0,score_detail=["correct"])
        metrics=SimpleNamespace(outcome="OUTCOME_OK",total_time_ms=5,step_count=1,tool_call_count=1,verifier_verdict=None,steps_detail=[{"step":1,"tool":"read","args":{"path":"/x"},"plan":"inspect"}])
        task=Task(id="fixture",input="fixture")
        with patch("bitgn_agent.run_agent",return_value=metrics):
            trajectory=obj.solve(task)
        cached=trajectory.conversation[0]
        self.assertEqual(cached["score"],1.0)
        self.assertEqual(cached["task_description"],"fixture task")
        self.assertEqual(cached["agent_metrics"]["tool_call_count"],1)
        adapter=BitgnBenchmarkAdapter.__new__(BitgnBenchmarkAdapter)
        feedback=adapter.evaluate(task,trajectory)
        self.assertTrue(feedback.success)
        self.assertIn("[STEP] 1 read",feedback.detail)
        obj._harness_client.end_trial.assert_called_once()

    def test_legacy_trajectory_remains_supported(self):
        adapter=BitgnBenchmarkAdapter.__new__(BitgnBenchmarkAdapter)
        task=Task(id="fixture",input="fixture")
        trajectory=Trajectory(task_id="fixture",output="",conversation=[{"score":0.5,"detail":["partial"]}])
        feedback=adapter.evaluate(task,trajectory)
        self.assertEqual(feedback.score,0.5)
        self.assertFalse(feedback.success)


if __name__ == "__main__":
    unittest.main()
