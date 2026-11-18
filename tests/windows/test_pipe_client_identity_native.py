"""Windows CI-only ephemeral named-pipe identity smoke.

Uses the current disposable CI account on both endpoints. Does NOT create an
SCM service, user, ACL, registry key, CNG/TPM key or protected Owner authority.
This native API test cannot attest the user's Windows 11 trust environment.
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path
import unittest


@unittest.skipUnless(os.name == "nt", "Windows-only ephemeral pipe smoke")
class NativePipeIdentificationTests(unittest.TestCase):
    def test_exact_header_then_pipe_client_sid_and_revert(self):
        import ctypes as c
        from ctypes import wintypes as w

        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root / "src"))
        from my_local_ai.state.consent import _WindowsBrokerAPI

        api = _WindowsBrokerAPI()
        kernel, advapi = api.kernel, api.advapi
        create = api._bind(kernel, "CreateNamedPipeW",
            [w.LPCWSTR, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD,
             w.DWORD, c.c_void_p], w.HANDLE)
        open_client = api._bind(kernel, "CreateFileW",
            [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p, w.DWORD,
             w.DWORD, w.HANDLE], w.HANDLE)
        connect = api._bind(kernel, "ConnectNamedPipe",
            [w.HANDLE, c.c_void_p], w.BOOL)
        write = api._bind(kernel, "WriteFile",
            [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD),
             c.c_void_p], w.BOOL)
        read = api._bind(kernel, "ReadFile",
            [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD),
             c.c_void_p], w.BOOL)
        get_process = api._bind(kernel, "GetCurrentProcess", [], w.HANDLE)
        get_thread = api._bind(kernel, "GetCurrentThread", [], w.HANDLE)
        open_thread = api._bind(advapi, "OpenThreadToken",
            [w.HANDLE, w.DWORD, w.BOOL, c.POINTER(w.HANDLE)], w.BOOL)
        pipe = client = None
        bad_handle = c.c_void_p(-1).value
        name = r"\\.\pipe\MLA-CI-readonly-identity-" + secrets.token_hex(12)
        try:
            pipe = create(name, 3, 0, 1, 4096, 4096, 1000, None)
            self.assertNotIn(pipe, (None, bad_handle),
                             f"CreateNamedPipeW: {c.get_last_error()}")
            # Open with exact FILE_READ_DATA / FILE_WRITE_DATA, not generic
            # write (which carries FILE_CREATE_PIPE_INSTANCE).
            # SECURITY_SQOS_PRESENT + SECURITY_IDENTIFICATION makes the
            # temporary server identity query non-privilege-bearing.
            client = open_client(name, 0x3, 0, None, 3, 0x00110000, None)
            self.assertNotIn(client, (None, bad_handle),
                             f"CreateFileW: {c.get_last_error()}")
            if not connect(pipe, None):
                self.assertEqual(c.get_last_error(), 535)  # PIPE_CONNECTED
            header = c.create_string_buffer(b"\x04\x00\x00\x00")
            sent, received = w.DWORD(), w.DWORD()
            self.assertTrue(write(client, header, 4, c.byref(sent), None))
            self.assertEqual(sent.value, 4)
            observed = c.create_string_buffer(4)
            self.assertTrue(read(pipe, observed, 4, c.byref(received), None))
            self.assertEqual(received.value, 4)
            self.assertEqual(observed.raw, b"\x04\x00\x00\x00")

            expected = api.process_sid(get_process())
            self.assertEqual(api.pipe_client_sid_after_read(pipe), expected)
            token = w.HANDLE()
            # RevertToSelf must leave the server thread with no open
            # impersonation token; otherwise service work must never run.
            self.assertFalse(open_thread(get_thread(), 0x0008, True,
                                         c.byref(token)))
            self.assertEqual(c.get_last_error(), 1008)  # ERROR_NO_TOKEN
            print("EPHEMERAL_PIPE_SID_AND_REVERT_PASS_NO_OWNER_TRUST")
        finally:
            for handle in (client, pipe):
                if handle not in (None, bad_handle):
                    kernel.CloseHandle(handle)


if __name__ == "__main__":
    unittest.main()
