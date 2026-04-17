from apify_client import ApifyClient
from config import get_apify_token


def run_actor(actor_id: str, run_input: dict, timeout_secs: int = 300) -> list[dict]:
    """Run an Apify actor and return its dataset items.

    Uses .call() which blocks with internal backoff until the run finishes.
    """
    client = ApifyClient(get_apify_token())
    run = client.actor(actor_id).call(
        run_input=run_input,
        timeout_secs=timeout_secs,
    )
    # Accept partial results from timed-out or aborted runs
    status = run["status"]
    if status not in ("SUCCEEDED", "TIMED-OUT", "ABORTED"):
        raise RuntimeError(f"Apify actor {actor_id} failed: {status}")
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    if status != "SUCCEEDED":
        print(f"({status}, got {len(items)} partial results)", end=" ")
    return items
