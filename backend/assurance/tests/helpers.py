from assurance.tasks import execute_assurance_run


def execute_to_completion(run_id):
    for _ in range(1000):
        result = execute_assurance_run.run(run_id)
        if result["status"] != "RUNNING":
            return result
    raise AssertionError("Assurance did not terminate")
