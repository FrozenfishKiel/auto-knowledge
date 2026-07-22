from open_webui.events import EVENTS, EVENT_CATALOG_SET


def test_auto_knowledge_audit_events_are_registered():
    expected = {
        "auto_knowledge.job.created",
        "auto_knowledge.job.updated",
        "auto_knowledge.job.deleted",
        "auto_knowledge.job.run_requested",
        "auto_knowledge.job.run_completed",
        "auto_knowledge.job.run_failed",
        "auto_knowledge.candidate.approved",
        "auto_knowledge.candidate.rejected",
        "auto_knowledge.candidate.published",
    }

    assert EVENTS.AUTO_KNOWLEDGE_JOB_CREATED.name == "auto_knowledge.job.created"
    assert expected.issubset(EVENT_CATALOG_SET)
