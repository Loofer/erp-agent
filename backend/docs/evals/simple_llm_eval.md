# Evaluate a Simple LLM‑Application
This guide explains a simple workflow for testing and evaluating LLM‑applications using Ragas. It assumes minimal prior knowledge of building and evaluating AI applications. Please refer to our installation instructions to install Ragas.

## Get a Working Example
To quickly see these concepts in action, create a project with the quickstart command.

### uvx (Recommended)
First install Ragas
```bash
uvx ragas quickstart rag_eval
cd rag_eval
uv sync
```

This generates a complete project with example code. Follow this guide to understand what is happening in the generated code. Let’s get started!

## Project Structure
Below is what gets created for you:
```
rag_eval/
├── README.md             # Project documentation and setup instructions
├── pyproject.toml        # Project configuration for uv and pip
├── evals.py              # Your evaluation workflow
├── rag.py                # Your RAG/LLM application
├── __init__.py           # Makes this a Python package
└── evals/                # Evaluation artifacts
    ├── datasets/         # Test data files (optional)
    ├── experiments/      # Results from running evaluations (CSV files saved here)
    └── logs/             # Evaluation execution logs
```

### Key Files to Focus On
- **evals.py** — Your evaluation workflow, including dataset loading and evaluation logic
- **rag.py** — Your RAG/LLM application code (query engine, retrieval, etc.)

## Understanding the Code
Inside `evals.py` from your generated project, you will see the main workflow pattern:
1. **Load dataset** — Define test cases using `SingleTurnSample`
2. **Query the RAG system** — Obtain responses from your application
3. **Evaluate responses** — Validate responses against ground‑truth references
4. **Display results** — Print evaluation summary to console
5. **Save results** — Automatically export CSV outputs into `evals/experiments/`

The template provides modular functions ready for customization.
```python
from ragas.dataset_schema import SingleTurnSample
from ragas import EvaluationDataset

def load_dataset():
    """Load test dataset for evaluation."""
    data_samples = [
        SingleTurnSample(
            user_input="What is Ragas?",
            response="",  # Will be filled by querying RAG
            reference="Ragas is an evaluation framework for LLM applications",
            retrieved_contexts=[],
        ),
        # Add more test cases...
    ]
    return EvaluationDataset(samples=data_samples)
```

You can extend this with metrics and more complex evaluation logic. Read more about evaluations in Ragas.

## Choose your LLM Provider
The quickstart project initializes the OpenAI LLM by default inside the `_init_clients()` function. You can easily switch to any provider via `llm_factory`.
- OpenAI
- Anthropic Claude
- Google Gemini
- Local models (Ollama)
- Custom / other providers

Set your OpenAI API key:
```bash
export OPENAI_API_KEY="your-openai-key"
```

Inside `_init_clients()` in `evals.py`:
```python
from ragas.llms import llm_factory

llm = llm_factory("gpt-4o")
```
This is already configured in your quickstart project.

## Use Pre‑built Metrics
Ragas comes with pre‑built metrics for common evaluation tasks. For example, **Aspect Critique** uses `DiscreteMetric` to evaluate any aspect of your output.

```python
from ragas.metrics import DiscreteMetric
from ragas.llms import llm_factory

# Setup your evaluator LLM
evaluator_llm = llm_factory("gpt-4o")

# Create a custom aspect evaluator
metric = DiscreteMetric(
    name="summary_accuracy",
    allowed_values=["accurate", "inaccurate"],
    prompt="""Evaluate if the summary is accurate and captures key information.

Response: {response}

Answer with only 'accurate' or 'inaccurate'.""",
    llm=evaluator_llm
)

# Score your application's output
score = await metric.ascore(
    response="The summary of the text is..."
)
print(f"Score: {score.value}")  # 'accurate' or 'inaccurate'
print(f"Reason: {score.reason}")
```

Pre‑built metrics like this avoid writing evaluation logic from scratch. Explore all available metrics.

> **Info**
> Many other types of metrics are available in Ragas (reference‑based and reference‑free). You may also build custom metrics if none fit your use‑case. Learn more about metrics.

## Evaluate over a Dataset
In your quickstart project, the `load_dataset()` function creates test data with multiple samples.

```python
from ragas import Dataset

# Create a dataset with multiple test samples
dataset = Dataset(
    name="test_dataset",
    backend="local/csv",  # Can also use JSONL, Google Drive, or in‑memory
    root_dir=".",
)

# Add samples to the dataset
data_samples = [
    {
        "user_input": "What is ragas?",
        "response": "Ragas is an evaluation framework...",
        "expected": "Ragas provides objective metrics..."
    },
    {
        "user_input": "How do metrics work?",
        "response": "Metrics score your application...",
        "expected": "Metrics evaluate performance..."
    },
]

for sample in data_samples:
    dataset.append(sample)

# Save to disk
dataset.save()
```

This lets you evaluate many test cases instead of one at a time. Read more about datasets and experiments.

Your generated project includes sample data inside the `evals/datasets/` folder — edit these files to add additional test cases.
