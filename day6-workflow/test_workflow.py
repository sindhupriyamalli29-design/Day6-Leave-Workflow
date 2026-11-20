import pytest
import leave_workflow as workflow


def test_policy_has_ten_sections():
    sections = workflow.load_sections()
    assert len(sections) == 10


@pytest.mark.parametrize(
    "question, expected_section",
    [
        ("Can I carry over unused leave?", "7"),
        ("Who approves my leave if my manager is on leave?", "4"),
        ("Can I take half a day of sick leave?", "3"),
        ("How many days in advance must I apply for casual leave?", "2"),
    ]
)
def test_retrieval(question, expected_section):
    sections = workflow.load_sections()
    result = workflow.retrieve(question, sections)
    assert result["matches"][0]["section"]["number"] == expected_section


def test_unrelated_question():
    sections = workflow.load_sections()
    result = workflow.retrieve(
        "What's the canteen menu today?",
        sections
    )
    assert result["context"] == "NO MATCHING SECTION"


def test_valid_json():
    draft = workflow.parse_draft({
        "answer": "Yes, casual leave can be carried over.",
        "source_section": "7",
        "confidence": "high"
    })
    assert draft["source_section"] == "7"


def test_invalid_json():
    with pytest.raises(ValueError):
        workflow.parse_draft({
            "answer": "Test",
            "confidence": "high"
        })


def test_rejection_does_not_send(monkeypatch):
    monkeypatch.setattr(
        workflow,
        "get_draft",
        lambda question, context: {
            "answer": "Test answer",
            "source_section": "7",
            "confidence": "high"
        }
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: "n"
    )

    def prevent_sending(question, draft):
        pytest.fail("Rejected request must not be sent")

    monkeypatch.setattr(
        workflow,
        "send_to_mock_api",
        prevent_sending
    )

    result = workflow.run_question(
        "Can I carry over unused leave?"
    )

    assert result["status"] == "Rejected"
