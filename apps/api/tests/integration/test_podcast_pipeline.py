from api.services.intel.podcast_intelligence import ConversationSegment, analyze_segments


def test_podcast_analysis_to_director_input_contract():
    analysis = analyze_segments(
        "upload-1",
        [ConversationSegment(0, 10, "Why did you start the company?", "host")],
    )
    assert analysis.scenes[0].signals["content_type"] == "podcast"
    assert analysis.candidates[0].scores["kind"] == "question_answer"
