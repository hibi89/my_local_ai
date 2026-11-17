"""Mocked resource sampling, NOT actual Windows/24-hour acceptance."""
import unittest

from my_local_ai.ops.resource_monitor import (
    ResourceLimits,ResourceReading,assess_resources,
)
from my_local_ai.ops.supervisor import assess_supervisor

LIMITS=ResourceLimits(max_ram_mb=12288,max_vram_mb=3072,
                      max_temperature_c=85.0,max_cpu_percent=95.0)


def reading(**changes):
    args=dict(ram_mb=4500.0,vram_mb=2100.0,temperature_c=67.0,
              cpu_percent=61.0,source="SYNTHETIC_UNKNOWN")
    args.update(changes)
    return ResourceReading(**args)


def supervise(**changes):
    args=dict(resource_reading=reading(),resource_limits=LIMITS,
              code_ready=True,lease_epoch=1,attempts=1)
    args.update(changes)
    return assess_supervisor(**args)


class ResourceSupervisorFixtureTests(unittest.TestCase):
    def test_synthetic_healthy_reading_never_grants_start(self):
        out=assess_resources(reading(),LIMITS)
        self.assertEqual(out.state,"WITHIN_DECLARED_LIMITS_UNVERIFIED")
        self.assertFalse(out.may_start_worker)
        self.assertFalse(out.real_measurement_verified)
        proposal=supervise()
        self.assertEqual(proposal.state,"READY_CODE_ONLY")
        self.assertFalse(proposal.auto_restart_allowed)
        self.assertFalse(proposal.long_run_verified)

    def test_unknown_sensors_and_thermal_pressure_hold(self):
        for change in (
            {"ram_mb":None}, {"vram_mb":None}, {"temperature_c":None},
            {"cpu_percent":None}, {"temperature_c":95.0},
            {"vram_mb":3800.0}, {"ram_mb":16000.0}, {"cpu_percent":100.0},
        ):
            with self.subTest(change=change):
                out=supervise(resource_reading=reading(**change))
                self.assertEqual(out.state,"RESOURCE_HOLD")
                self.assertFalse(out.process_signal_allowed)

    def test_nonfinite_and_negative_sensors_hold(self):
        for value in (float("nan"),float("inf"),-1,True,"95"):
            with self.subTest(value=value):
                out=assess_resources(reading(temperature_c=value),LIMITS)
                self.assertEqual(out.state,"HOLD")

    def test_claimed_owner_approval_is_not_protected_signer(self):
        result=supervise(owner_go_claimed=True)
        self.assertEqual(result.state,"OWNER_CLAIM_UNVERIFIED")
        self.assertFalse(result.operator_go_verified)
        self.assertFalse(result.auto_restart_allowed)

    def test_repair_exhaustion_and_missing_lease_prevent_restart(self):
        self.assertEqual(supervise(attempts=2).state,"REPAIR_EXHAUSTED")
        self.assertEqual(supervise(lease_epoch=0).state,"NO_TRUSTED_LEASE")
        self.assertEqual(supervise(code_ready=False).state,"CODE_NOT_READY")

    def test_no_24_hour_claim_from_24_synthetic_samples(self):
        for sample in range(24):
            out=supervise(resource_reading=reading(cpu_percent=60+sample/10))
            self.assertFalse(out.long_run_verified)
            self.assertFalse(out.network_allowed)
        self.assertEqual(sample,23)

    def test_invalid_policy_and_wrong_source_fail(self):
        for maximum in (0,True,float("inf")):
            with self.assertRaises(ValueError):
                ResourceLimits(max_ram_mb=maximum)
        with self.assertRaises(ValueError):
            assess_resources(reading(source="UNTRUSTED_MODEL_JSON"),LIMITS)


if __name__=="__main__":
    unittest.main()
