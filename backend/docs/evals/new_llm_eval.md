# How to Evaluate a New LLM for Your Use‑Case
When a new LLM is released, you may want to determine whether it outperforms your current model for your specific use‑case. This guide shows you how to perform accuracy comparisons between two LLMs using the Ragas framework.

## What You Will Accomplish
After completing this guide, you will be able to:
- Set up structured evaluations to compare two LLMs
- Assess model performance on real‑world business tasks
- Generate detailed results to inform your model‑selection decisions
- Maintain a reusable evaluation loop that you can re‑run whenever new LLMs are released

## Evaluation Scenario
We use discount calculation as our test case: given a customer profile, compute the appropriate discount percentage and explain the reasoning. This task requires rule‑application and reasoning‑capabilities — skills that differentiate model performance.

> **Note**: You can adapt this approach to any use‑case important to your application.

📁 **Full Code**: The complete source code for this example is available on GitHub.

## Set‑up Environment and API Access
First install the `ragas‑examples` package containing benchmark‑LLM sample code.
```bash
pip install ragas[examples]
```

Next ensure your API credentials are configured:
```bash
export OPENAI_API_KEY=your_actual_api_key
```

## LLM Application
A simple LLM application is provided within the example package so you can focus on evaluation instead of building the application itself. The application computes customer discounts following business rules.

This is the system prompt defining discount‑calculation logic:
```python
SYSTEM_PROMPT = """
You are a discount calculation assistant. I will provide a customer profile and you must calculate their discount percentage and explain your reasoning.

Discount rules:
- Age 65+ OR student status: 15% discount
- Annual income < $30,000: 20% discount
- Premium member for 2+ years: 10% discount
- New customer (< 6 months): 5% discount

Rules can stack up to a maximum of 35% discount.

Respond in JSON format only:
{
  "discount_percentage": number,
  "reason": "clear explanation of which rules apply and calculations",
  "applied_rules": ["list", "of", "applied", "rule", "names"]
}
"""
```

Test the application with a sample customer profile:
```python
from ragas_examples.benchmark_llm.prompt import run_prompt

# Test with a sample customer profile
customer_profile = """
Customer Profile:
- Name: Sarah Johnson
- Age: 67
- Student: No
- Annual Income: $45,000
- Premium Member: Yes, for 3 years
- Account Age: 3 years
"""

result = await run_prompt(customer_profile)
print(result)
```

## Inspect the Evaluation Dataset
For this evaluation, a synthetic dataset is built containing:
- Simple cases with unambiguous outcomes
- Edge‑cases sitting on rule boundaries
- Complex scenarios with ambiguous information

Each entry specifies:
- `customer_profile`: input data
- `expected_discount`: target discount percentage
- `description`: indicator of case complexity

Example dataset structure (add an `id` column for easy comparison):

| ID | Customer Profile | Expected Discount | Description |
|---|---|---|---|
|1|Martha is a 70‑year‑old retiree who enjoys gardening. She is not enrolled in any academic programs, has an annual pension of $50 000, signed up for our service nine years ago, and has never upgraded to premium membership.|15|Senior‑only|
|2|Arjun, 19, is a full‑time computer‑science undergraduate. His part‑time job yields around $45 000 per year. He opened his account one year ago and has no premium membership.|15|Student‑only|
|3|Cynthia is a 40‑year‑old freelance artist earning approximately $25 000 per year. She is not studying anywhere, subscribed to our basic plan five years ago, and has never upgraded to premium membership.|20|Low‑income‑only|

To customise the dataset for your own use‑case, create a `datasets/` directory and add your CSV files. Refer to Core Concepts — Evaluation Datasets for more details.

Best practice: sample real‑world data from your application to build your dataset. If real data is unavailable, generate synthetic data using an LLM. For moderately complex use‑cases, use a capable model such as `gpt‑5‑high` to generate higher‑quality synthetic data. Always manually review and validate generated data.

> **Note**:
> While the example dataset in this guide contains roughly 10 cases for brevity, for real‑world evaluations start with 20‑30 samples and iteratively expand to 50‑100 samples for trustworthy results. Ensure broad coverage of scenarios your agent may encounter, including edge‑cases and complex questions. You do not need 100% initial accuracy; use results for error‑analysis and iteratively improve prompts, data and tooling.

### Load the Dataset
```python
def load_dataset():
    """Load the dataset from CSV file. Downloads from GitHub if not found locally."""
    import urllib.request
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_path = os.path.join(current_dir, "datasets", "discount_benchmark.csv")
    # Download dataset from GitHub if it doesn't exist locally
    if not os.path.exists(dataset_path):
        os.makedirs(os.path.dirname(dataset_path), exist_ok=True)
        urllib.request.urlretrieve("https://raw.githubusercontent.com/vibrantlabsai/ragas/main/examples/ragas_examples/benchmark_llm/datasets/discount_benchmark.csv", dataset_path)
    return Dataset.load(name="discount_benchmark", backend="local/csv", root_dir=current_dir)
```
The dataset loader checks for a local CSV file and automatically downloads it from GitHub if missing.

## Metric Function
It is recommended to use a simple, use‑case‑relevant metric. See Core Concepts — Metrics for further information. This accuracy metric scores each response:
```python
from ragas.metrics import discrete_metric
from ragas.metrics.result import MetricResult

@discrete_metric(name="discount_accuracy", allowed_values=["correct", "incorrect"])
def discount_accuracy(prediction: str, expected_discount):
    """Check if the discount prediction is correct."""
    import json

    parsed_json = json.loads(prediction)
    predicted_discount = parsed_json.get("discount_percentage")
    expected_discount_int = int(expected_discount)

    if predicted_discount == expected_discount_int:
        return MetricResult(
            value="correct",
            reason=f"Correctly calculated discount={expected_discount_int}%"
        )
    else:
        return MetricResult(
            value="incorrect",
            reason=f"Expected discount={expected_discount_int}%; Got discount={predicted_discount}%"
        )
```

## Experiment Structure
Each model evaluation follows this experiment pattern:
```python
import json
from ragas import experiment

@experiment()
async def benchmark_experiment(row, model_name: str):
    # Get model response
    response = await run_prompt(row["customer_profile"], model=model_name)

    # Parse response (strict JSON mode expected)
    try:
        parsed_json = json.loads(response)
        predicted_discount = parsed_json.get('discount_percentage')
    except Exception:
        predicted_discount = None

    # Score the response
    score = discount_accuracy.score(
        prediction=response,
        expected_discount=row["expected_discount"]
    )

    return {
        **row,
        "model": model_name,
        "response": response,
        "predicted_discount": predicted_discount,
        "score": score.value,
        "score_reason": score.reason
    }
```

## Run the Experiment
Run evaluation experiments for both baseline and candidate models. In this example we compare:
- Baseline model: `"gpt‑4.1‑nano‑2025‑04‑14"`
- Candidate model: `"gpt‑5‑nano‑2025‑08‑07"`

```python
from ragas_examples.benchmark_llm.evals import benchmark_experiment, load_dataset

# Load dataset
dataset = load_dataset()
print(f"Dataset loaded with {len(dataset)} samples")

# Run baseline experiment
baseline_results = await benchmark_experiment.arun(
    dataset,
    name="gpt-4.1-nano-2025-04-14",
    model_name="gpt-4.1-nano-2025-04-14"
)

# Calculate and display accuracy
baseline_accuracy = sum(1 for r in baseline_results if r["score"] == "correct") / len(baseline_results)
print(f"Baseline Accuracy: {baseline_accuracy:.2%}")

# Run candidate experiment
candidate_results = await benchmark_experiment.arun(
    dataset,
    name="gpt-5-nano-2025-08-07",
    model_name="gpt-5-nano-2025-08-07"
)

# Calculate and display accuracy
candidate_accuracy = sum(1 for r in candidate_results if r["score"] == "correct") / len(candidate_results)
print(f"Candidate Accuracy: {candidate_accuracy:.2%}")
```

Each experiment saves a CSV file under the `experiments/` directory containing:
`id, model, response, predicted_discount, score, score_reason`

> **Note**:
> Where possible, fix and log exact model snapshots / versions (e.g. use `"gpt‑4o‑2024‑08‑06"` instead of just `"gpt‑4o"`). Providers regularly update aliases and performance can shift between snapshots. Include snapshot identifiers in your results to enable fair, reproducible future comparisons. Consult your provider’s model documentation for available snapshots.

## Compare Results
After running experiments with different models, compare performance side‑by‑side:
```python
from ragas_examples.benchmark_llm.evals import compare_inputs_to_output

# Compare the two experiment results
# Update these paths to match your actual experiment output files
output_path = compare_inputs_to_output(
    inputs=[
        "experiments/gpt-4.1-nano-2025-04-14.csv",
        "experiments/gpt-5-nano-2025-08-07.csv"
    ]
)

print(f"Comparison saved to: {output_path}")
```

This comparison will:
1. Read both experiment files
2. Print accuracy metrics for each model
3. Generate a new CSV file with side‑by‑side results

The comparison CSV includes:
- Test‑case details (customer profile, expected discount)
- For each model: its raw response, pass/fail status and scoring reason

## Analyse Results Using the Merged CSV
In this example run:
- Filter cases where one model outperforms the other; examples include “senior + new‑customer”, “student + new‑customer”, “student‑only”, “premium‑member ≥2 years”.
- Inspect the `reason` field from each model response to understand its output logic.
- Look for failure patterns (e.g. mis‑applied stacked rules, boundary‑condition errors near age or income thresholds).

## Re‑Run When New LLMs Are Released
Once this evaluation workflow lives alongside your project, it becomes a repeatable check. When new LLMs are released (frequently nowadays), plug them in as candidate‑models and re‑run the same evaluation against your fixed baseline.

## Interpret Results and Make Decisions
### What to look for
- Baseline accuracy vs candidate accuracy and the delta.
- Example from our run: Baseline 50 % (5/10), Candidate 90 % (9/10), delta +40 %.

### How to read individual rows
- Focus on rows where model outputs disagree.
- Use `score_reason` to understand why each case was marked correct / incorrect.
- Identify recurring failure patterns (rule stacking, boundary thresholds etc.).

### Beyond raw accuracy
Also examine **cost and latency**. Higher accuracy may not be worthwhile if latency or cost becomes prohibitive.

### Decision‑making guidance
- Switch if the new model delivers substantially better accuracy on your high‑priority cases while satisfying cost/latency constraints.
- Keep your existing model if gains are minor, critical cases still fail, or cost/latency regress.

> In our example: we would switch to `"gpt‑5‑nano‑2025‑08‑07"`. It lifts accuracy from 50 % to 90 % (+40 %) and fixes key failure modes such as mishandled rule stacking and boundary‑conditions — provided latency and cost fit your constraints.

## Adapt to Your Own Use‑Case
Use the GitHub code as a template and adapt it to your application‑specific logic.

The Ragas framework handles orchestration, parallel‑execution and result‑aggregation automatically, letting you focus on evaluation and your business requirements.
