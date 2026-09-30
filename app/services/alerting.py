import logging
logger =  logging.getLogger("onboarding.alerts")

def alert_supervisor(step_name: str, crm_deal_id: str, error_message: str) -> None:
    """Supervisor alert. Currently a clear logo, later we will replace it with Slack/Email."""
    logger.error(
        "SUPERVISOR ALERT | step=%s | deal=%s | error=%s",
        step_name,
        crm_deal_id,
        error_message,
    )