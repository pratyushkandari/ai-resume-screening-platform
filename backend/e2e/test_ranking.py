"""Ranking on the live stack (real embedding model) against the graded dataset."""

from evaluation.metrics import ndcg_at_k, precision_at_k

# The production row of the evaluation table in the README (`make eval`): the stack runs
# the same code and model, so the same resumes must rank the same way.
OFFLINE_NDCG_AT_10 = 0.930
OFFLINE_PRECISION_AT_5 = 0.960
TOLERANCE = 0.03  # room for float differences between CPUs and ties broken differently


def ranked_resume_ids(summary: dict, resumes: dict) -> list:
    """Dataset resume ids in dashboard order (candidates are identified by the name on line 1)."""
    by_name = {text.splitlines()[0].strip(): rid for rid, text in resumes.items()}
    return [by_name.get(c["candidate_name"]) for c in summary["candidates"]]


def test_every_upload_was_processed(evaluation_jobs):
    batches = evaluation_jobs["batches"]
    assert sum(b["successful"] for b in batches) == 250 and sum(b["failed"] for b in batches) == 0


def test_every_resume_is_parsed_and_ranked_with_semantic_scores(summaries, dataset):
    for job_id, summary in summaries.items():
        ranked = ranked_resume_ids(summary, dataset["resumes"])
        assert len(ranked) == 50 and None not in ranked, job_id
        assert summary["total_candidates"] == 50 and summary["semantic_available"] is True


def test_ranking_quality_matches_the_offline_evaluation(summaries, dataset):
    ndcgs, precisions = [], []
    for job_id, summary in summaries.items():
        grades = [dataset["labels"][(job_id, rid)] for rid in ranked_resume_ids(summary, dataset["resumes"])]
        ndcgs.append(ndcg_at_k(grades, 10))
        precisions.append(precision_at_k(grades, 5))
    assert abs(sum(ndcgs) / len(ndcgs) - OFFLINE_NDCG_AT_10) <= TOLERANCE, ndcgs
    assert abs(sum(precisions) / len(precisions) - OFFLINE_PRECISION_AT_5) <= TOLERANCE, precisions


def test_keyword_stuffed_resumes_stay_out_of_the_top_five(summaries, dataset):
    stuffers = {"r39", "r40", "r41"}  # list every keyword without the experience; grade 0 for every job
    for job_id, summary in summaries.items():
        assert not stuffers & set(ranked_resume_ids(summary, dataset["resumes"])[:5]), job_id


def test_dashboard_totals_agree_with_the_candidates(summaries):
    for summary in summaries.values():
        shortlisted = [c for c in summary["candidates"] if c["status"] == "accepted"]
        assert summary["shortlisted_candidates"] == len(shortlisted)
        assert summary["strong_fits"] == sum(c["score"] >= 0.80 for c in shortlisted)
        expected = {skill: sum(skill in c["matched_skills"] for c in summary["candidates"]) for skill in summary["job_skills"]}
        assert {s["skill_name"]: s["matches"] for s in summary["job_skill_counts"]} == expected


def test_evaluate_saves_rankings_in_dashboard_order(api, recruiter, evaluation_jobs, summaries):
    for job_id, api_id in evaluation_jobs["ids"].items():
        ranked = api.call("POST", f"/api/jobs/{api_id}/rank", headers=recruiter["headers"])
        assert ranked.status_code == 200 and ranked.json()["ranked"] >= 50
        url = f"/api/jobs/{api_id}"
        live = [c["resume_id"] for c in api.call("GET", f"{url}/summary", headers=recruiter["headers"]).json()["candidates"]]
        saved = [r["resume_id"] for r in api.call("GET", f"{url}/rankings", headers=recruiter["headers"]).json()]
        assert [rid for rid in saved if rid in set(live)] == live, job_id


def test_downloads_return_the_uploaded_bytes(api, recruiter, evaluation_jobs, summaries):
    candidates = summaries["backend"]["candidates"]
    for c in candidates[:3] + candidates[-3:]:
        r = api.call("GET", f"/api/resumes/{c['resume_id']}/download", headers=recruiter["headers"])
        rid = c["filename"].rsplit(".", 1)[0]
        assert r.status_code == 200 and r.content == evaluation_jobs["files"][rid][1], c["filename"]
        assert c["filename"] in r.headers["content-disposition"]
