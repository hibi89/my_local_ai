"""Immediate P1 host/guest separation checks. All Qwen responses are fake.

Never launches Windows Sandbox, modifies Windows ACLs, calls a real model,
writes a source file, creates a Git commit or asserts independent F18 PASS.
"""
from __future__ import annotations

from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from my_local_ai.ax_runtime import isolation_runner as runner
from my_local_ai.ax_runtime.budgets import BudgetGuard, ModelBudget
from my_local_ai.ax_runtime.opencode_worker import PreparedOpenCodeRun

SOURCE="a"*40
PLAN="f"*64


def _bundle():
    profile=runner.prepare_windows_no_egress_profile(
        task_id="TEST-001",run_id="RUN-001",role="CODER",
        source_sha=SOURCE,plan_sha256=PLAN,
    )
    prepared=PreparedOpenCodeRun(
        task_id="TEST-001",plan_sha256=PLAN,source_sha=SOURCE,
        allowed_paths=("src/demo.py",),worktree="C:/MLA_Scratch/test",
        argv=("opencode","run","--standalone","--archived",
              "--agent","build","--model","ollama/qwen3:4b-instruct",
              "--format","json","SYNTHETIC"),
        environment=(("OLLAMA_HOST","http://127.0.0.1:11434"),),
        prompt="SYNTHETIC",
    )
    transport=runner.prepare_offline_coder_transport(
        profile=profile,prepared=prepared,
    )
    request=runner.prepare_host_qwen_generation(
        transport,coding_request="Create a synthetic Python demo file."
    )
    return profile,transport,request


def _model_result(files, **extra):
    return json.dumps({
        "model":"qwen3:4b-instruct","done":True,
        "response":json.dumps({"version":1,"files":files}),
        **extra
    }).encode("utf-8")


class HostOnlyQwenBridgeTests(unittest.TestCase):
    def test_host_inference_makes_only_one_fixed_loopback_request(self):
        profile,transport,request=_bundle()
        expected = _model_result([{
            "path":"src/demo.py","content":"def answer():\n    return 42\n",
        }])
        calls=[]
        class FakeResponse:
            status=200
            def getheader(self,name,default=""):
                self_name = name.lower()
                return "application/json" if self_name=="content-type" else default
            def read(self,n):
                self_n=n
                return expected
        class FakeConnection:
            def __init__(self,host,port,timeout):
                calls.append(("connect",host,port,timeout))
            def request(self,method,path,body,headers):
                calls.append(("request",method,path,body,headers))
            def getresponse(self):
                return FakeResponse()
            def close(self):
                calls.append(("close",))
        budget=BudgetGuard(ModelBudget(max_calls=1))
        with patch.object(runner,"_HTTPConnection",FakeConnection):
            result=runner.infer_host_qwen_public_synthetic(
                request,transport,budget=budget,
            )
            with self.assertRaises(runner.WindowsIsolationHold):
                runner.infer_host_qwen_public_synthetic(
                    request,transport,budget=budget,
                )
        self.assertEqual(calls[0][:3],("connect","127.0.0.1",11434))
        self.assertEqual(calls[1][1:3],("POST","/api/generate"))
        self.assertEqual(
            json.loads(calls[1][3])["model"],"qwen3:4b-instruct"
        )
        self.assertEqual(result.files,(
            ("src/demo.py","def answer():\n    return 42\n"),
        ))
        self.assertFalse(result.files_applied_to_original)
        self.assertFalse(result.independent_f18_verified)
        self.assertFalse(result.can_publish)

    def test_injected_host_output_path_and_tool_calls_rejected(self):
        _,transport,request=_bundle()
        bad_outputs=(
            _model_result([{"path":"../.env","content":"exfil"}]),
            _model_result([{"path":"src/other.py","content":"exfil"}]),
            _model_result([{"path":"src/demo.py","content":"ok"}],
                          tool_calls=[{"name":"shell"}]),
            _model_result([
                {"path":"src/demo.py","content":"ok"},
                {"path":"src/demo.py","content":"modified"},
            ]),
            b'{"model":"qwen3:4b-instruct","done":true,"done":true}',
        )
        for raw in bad_outputs:
            with self.subTest(raw=raw[:80]):
                with self.assertRaises(runner.WindowsIsolationHold):
                    runner.decode_untrusted_host_qwen_files(
                        raw,request,transport,
                    )

    def test_public_synthetic_scope_rejects_remote_endpoint(self):
        _,transport,_=_bundle()
        with self.assertRaises(runner.WindowsIsolationHold):
            runner.prepare_host_qwen_generation(
                transport,coding_request="SYNTHETIC",
                endpoint_url="https://example.com",
            )
        with self.assertRaises(runner.WindowsIsolationHold):
            runner.prepare_host_qwen_generation(
                transport,coding_request="SYNTHETIC",
                classification="PRIVATE_CUSTOMER",
            )


class WindowsNoNetworkReadOnlyImportTests(unittest.TestCase):
    def test_readonly_guest_import_from_disposable_scratch(self):
        profile,transport,request=_bundle()
        patch_set=runner.decode_untrusted_host_qwen_files(
            _model_result([{"path":"src/demo.py","content":"pass\n"}]),
            request,transport,
        )
        import_plan=runner.prepare_sandbox_readonly_patch_import(
            profile=profile,proposed_files=patch_set,
            scratch_root=r"C:\MLA_Disposable",
        )
        self.assertIn("<Networking>Disable</Networking>",import_plan.config_xml)
        self.assertIn("<ReadOnly>true</ReadOnly>",import_plan.config_xml)
        self.assertIn("<MappedFolders>",import_plan.config_xml)
        self.assertNotIn("<ReadOnly>false",import_plan.config_xml)
        self.assertNotIn("<LogonCommand>",import_plan.config_xml)
        self.assertFalse(import_plan.host_scratch_acl_verified)
        self.assertFalse(import_plan.guest_isolation_attested)
        self.assertFalse(import_plan.may_promote)
        self.assertEqual(
            runner.audit_sandbox_readonly_patch_import(
                import_plan,profile=profile,proposed_files=patch_set,
            ),
            "EXACT_READ_ONLY_GUEST_IMPORT_HOST_ACL_AND_EGRESS_NOT_ATTESTED",
        )
        with self.assertRaises(runner.WindowsIsolationHold):
            runner.prepare_sandbox_readonly_patch_import(
                profile=profile,proposed_files=patch_set,
                scratch_root=r"C:\Users",
            )
        with self.assertRaises(runner.WindowsIsolationHold):
            runner.audit_sandbox_readonly_patch_import(
                replace(import_plan,config_xml=import_plan.config_xml.replace(
                    "<ReadOnly>true</ReadOnly>","<ReadOnly>false</ReadOnly>"
                )),profile=profile,proposed_files=patch_set,
            )


if __name__=="__main__":
    unittest.main()
