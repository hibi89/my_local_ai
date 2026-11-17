"""Zero-VM host-Qwen and Pure Player security contracts (synthetic only).

No real model, guest execution, Windows settings, OS key, Git promotion, or
remote connection is used by these tests.
"""
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from my_local_ai.ax_runtime import isolation_runner as runner
from my_local_ai.ax_runtime.budgets import BudgetGuard, ModelBudget
from my_local_ai.security.codeshield_contracts import (
    CodeShieldContext, CodeShieldHold, DataClass,
)

A="a"*40
B="b"*40
F="f"*64


def context():
    return CodeShieldContext(
        repository="hibi89/my_local_ai",
        task_id="TEST-001",run_id="RUN-001",
        owner_consent_ref="SYNTHETIC",
        plan_sha256=F,source_git_sha=A,candidate_git_sha=B,
        lease_epoch=1,nonce_sha256="c"*64,
        allowed_paths=("src/demo.py",),data_class=DataClass.PUBLIC_SYNTHETIC,
        scanner_pins=(),
    )


def _request():
    ctx=context()
    return ctx,runner.prepare_host_qwen_generation(
        ctx,run_id="RUN-001",coding_request="write synthetic demo",
    )


def _response(files,**extra):
    return json.dumps({
        "model":"qwen3:4b-instruct","done":True,
        "response":json.dumps({"version":1,"files":files}),**extra,
    }).encode()


class NoVMHostQwenTests(unittest.TestCase):
    def test_fixed_loopback_inference_without_guest(self):
        ctx,req=_request()
        expected=_response([{"path":"src/demo.py","content":"answer = 42\n"}])
        calls=[]
        class FakeResponse:
            status=200
            def getheader(self,name,default=""):
                return "application/json" if name.lower()=="content-type" else default
            def read(self,n):
                return expected
        class FakeConnection:
            def __init__(self,host,port,timeout):
                calls.append(("connect",host,port,timeout))
            def request(self,method,path,body,headers):
                calls.append(("request",method,path,json.loads(body)))
            def getresponse(self):
                return FakeResponse()
            def close(self):
                calls.append(("close",))
        budget=BudgetGuard(ModelBudget(max_calls=1))
        with patch.object(runner,"HTTPConnection",FakeConnection):
            files=runner.infer_host_qwen_public_synthetic(req,ctx,budget=budget)
            with self.assertRaises(runner.WindowsIsolationHold):
                runner.infer_host_qwen_public_synthetic(req,ctx,budget=budget)
        self.assertEqual(calls[0][:3],("connect","127.0.0.1",11434))
        self.assertEqual(calls[1][1:3],("POST","/api/generate"))
        self.assertEqual(files.files,(("src/demo.py","answer = 42\n"),))
        self.assertFalse(files.files_applied_to_original)
        self.assertFalse(files.generated_code_executed)
        self.assertFalse(files.independent_f18_verified)
        self.assertFalse(files.can_publish)

    def test_model_injection_and_path_escape_rejected(self):
        ctx,req=_request()
        for response in (
            _response([{"path":"../.env","content":"leak"}]),
            _response([{"path":"src/other.py","content":"leak"}]),
            _response([{"path":"src/demo.py","content":"x"}],
                      tool_calls=[{"name":"shell"}]),
            _response([{"path":"src/demo.py","content":"x"},
                       {"path":"src/demo.py","content":"y"}]),
            b'{"model":"qwen3:4b-instruct","done":true,"done":true}',
        ):
            with self.subTest(response=response[:40]),self.assertRaises(runner.WindowsIsolationHold):
                runner.decode_untrusted_host_qwen_files(response,req,ctx)

    def test_public_scope_and_remote_host_rejected(self):
        ctx,req=_request()
        for kw in ({"classification":"PRIVATE_CUSTOMER"},
                   {"endpoint_url":"https://example.com"},
                   {"model":"another-model"}):
            with self.subTest(kw=kw),self.assertRaises(runner.WindowsIsolationHold):
                runner.prepare_host_qwen_generation(
                    ctx,run_id="RUN-001",coding_request="synthetic",**kw,
                )

    def test_generated_text_to_pure_operator_stays_data_only(self):
        ctx,req=_request()
        output=runner.decode_untrusted_host_qwen_files(
            _response([{"path":"src/demo.py","content":"answer = 42\n"}]),req,ctx,
        )
        candidate=runner.prepare_pure_player_candidate(
            ctx,operator_id="STATIC_AST_REVIEW",proposed_files=dict(output.files),
        )
        result=runner.run_pure_player_nonexecuting_candidate(ctx,candidate)
        self.assertEqual(result["syntax"],"SYNTAX_SHAPE_ONLY")
        self.assertEqual(result["file_count"],1)
        self.assertFalse(result["generated_code_executed"])
        self.assertFalse(result["network_egress_allowed"])
        self.assertFalse(result["git_promotion_allowed"])

    def test_generated_binary_or_script_does_not_gain_execution(self):
        ctx=context()
        for op in ("RUN_CODE","HTTP_POST","WINDOWS_SANDBOX","APPCONTAINER","SHELL"):
            with self.subTest(op=op),self.assertRaises(CodeShieldHold):
                runner.deny_pure_player_network_operation(op)
        for bad in ({"../.env":"secret"},{"src/demo.py":"x\x00y"},
                    {"src/other.py":"x"}):
            with self.assertRaises(CodeShieldHold):
                runner.prepare_pure_player_candidate(
                    ctx,operator_id="STATIC_AST_REVIEW",proposed_files=bad,
                )
        safe=runner.prepare_pure_player_candidate(
            ctx,operator_id="STATIC_AST_REVIEW",proposed_files={"src/demo.py":"x=1"},
        )
        with self.assertRaises(CodeShieldHold):
            runner.run_pure_player_nonexecuting_candidate(
                ctx,replace(safe,payload_sha256="0"*64),
            )
        with self.assertRaises(runner.WindowsIsolationHold):
            replace(safe,network_egress_attested=True)


if __name__=="__main__":
    unittest.main()
