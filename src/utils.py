from datasets import Dataset
from datasets import load_dataset

async def load_data(
    split: str = "train",
    max_items: int = 10,
    min_score: int = 20,
    max_length: int = 8192,
    tokenizer_name: str = BASE_MODEL,
) -> Dataset:
    """Loads, preprocesses, and filters the dataset."""
    print(
        f"Loading data for split: {split}, max_items: {max_items}, tokenizer: {tokenizer_name}"
    )
    data: Dataset = load_dataset(
        "../data/fhir-single-turn", split=split
    )
    if not data:
        raise ValueError(f"No data loaded for split {split}. Check pull_data function.")

    # Ensure 'scraped_body' exists and is text
    def check_scraped_body(x):
        body = x.get("scraped_body")
        return isinstance(body, str) and len(body.strip()) > 0

    data = data.filter(check_scraped_body)
    if not data:
        raise ValueError(
            f"No data remaining after filtering for valid 'scraped_body' in split {split}."
        )

    data = data.map(
        lambda x: {
            "prompt": prompt_for_title(
                x["scraped_body"]
            ),  # Creates the list of messages
            "row": x,  # Keep original row data
        }
    )
    return filter_on_length(data, max_length, tokenizer_name)