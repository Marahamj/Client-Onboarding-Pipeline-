import os
FORCE_FAIL_STEP = os.getenv("FORCE_FAIL_STEP")
_call_counts: dict[str, int] = {}
def execute_mock_step(
    
    crm_deal_id: str,
    step_name: str,
    idempotency_key: str,
    fail_until_attempt: int = 0,
) -> dict[str, str]:
    """ Simulate external resource creation.
       fail_until_attempt: The number of attempts that deliberately fail before succeeding.
       0 = Never fail (default, preserves old behavior)."""
    if step_name == FORCE_FAIL_STEP:
        raise ConnectionError(
        f"Simulated outage for step: {step_name}"
        )
       
    _call_counts[idempotency_key] = _call_counts.get(idempotency_key,0)+1
    current_attempt = _call_counts[idempotency_key]
    if current_attempt <= fail_until_attempt:
        raise ConnectionError(
        f"Simulated failure #{current_attempt} for {step_name} ({crm_deal_id})"
        )
 
    external_id = f"mock-{step_name}-{crm_deal_id}"
        
    return {
       "external_id": external_id,
       "external_url": f"https://mock.example.com/{step_name}/{crm_deal_id}",
        }    
    
    