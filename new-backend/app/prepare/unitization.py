import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.orchestration import gpt
from pydantic import BaseModel
from app.embeddings import util 

class UnitizedSentence(BaseModel):
    sentence_id: int | str
    units: list[str]


class UnitizationBatchResult(BaseModel):
    results: list[UnitizedSentence]


DEFAULT_INPUT_PATH = "app/assets/resources/unique_sentences.json"
DEFAULT_OUTPUT_PATH = "app/assets/resources/provisions.json"
DEFAULT_BATCH_SIZE = 20
DEFAULT_MAX_CONCURRENT_BATCHES = 2
DEFAULT_CHECKPOINT_EVERY_BATCHES = 1


instruction = """
Task
Receive a JSON array of English source sentences and return the smallest meaningful information units for each sentence as atomic propositions.

Workflow
- Read each full source sentence before splitting.
- Identify explicit information only.
- Split compound statements joined by conjunctions, commas, relative clauses, lists, conditions, qualifications, or multiple predicates.
- Convert each unit into a complete and independent English sentence.
- Preserve terminology and phrasing from the source text as exactly as possible.
- Return one unit per line.
Unit Rules
- Keep each unit atomic: one clear proposition per line.
- Preserve the source text's modality and qualifiers, including terms such as must, shall, may, with, without, under, in, from, free from, and bracketed placeholders.
- Keep technical terms unchanged.
- Keep named authorities, countries, zones, diseases, establishments, and product terms unchanged.
- Repeat the subject as needed so each unit stands alone.
- Do not infer information that is not explicitly stated.
- Do not summarize, paraphrase, translate, explain, number, or group the units unless the user asks.
Output Format
Return JSON that matches the requested schema.
For each input item, preserve the exact sentence_id and return its unitized propositions in units.

Example
Source sentence:

The meat has derived from animals reared in country/ zone which is free from foot-and-mouth disease, African swine fever and classical swine fever.
Output:

The meat has derived from animals reared in country/ zone which is free from foot-and-mouth disease.
The meat has derived from animals reared in country/ zone which is free from African swine fever.
The meat has derived from animals reared in country/ zone which is free from classical swine fever.
"""


def build_unitizer() -> gpt.GPT:
    return gpt.GPT(
        name="Unitizer",
        role="You are a helpful assistant that splits English text into atomic propositions.",
        instructions=instruction,
        model='gpt-4.1-mini',
        output_type=UnitizationBatchResult,
        max_tokens=12000,
    )


def chunks(items: list[dict], size: int) -> Iterable[list[dict]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def sentence_key(sentence: dict) -> int | str:
    return sentence.get("sentence_id") or sentence.get("id") or sentence["sentence"]


def load_existing_results(output_path: str) -> dict[str, dict]:
    path = Path(output_path)
    if not path.exists():
        return {}

    existing = util.read_json_file(output_path)
    if isinstance(existing, dict):
        existing = existing.get("sentences", existing.get("results", []))

    processed = {}
    for item in existing:
        if isinstance(item, dict) and item.get("units"):
            processed[str(sentence_key(item))] = item
    return processed


def write_results(output_path: str, original_order: list[dict], processed: dict[str, dict]) -> None:
    ordered_results = [
        processed[str(sentence_key(sentence))]
        for sentence in original_order
        if str(sentence_key(sentence)) in processed
    ]
    util.write_json_file(output_path, ordered_results)


async def unitize_batch(
    unitizer: gpt.GPT,
    batch: list[dict],
    *,
    retries: int = 3,
) -> list[UnitizedSentence]:
    payload = [
        {
            "sentence_id": sentence_key(sentence),
            "sentence": sentence["sentence"],
        }
        for sentence in batch
    ]
    prompt = (
        "Split each sentence in this JSON array into atomic propositions. "
        "Return one result object per input sentence_id.\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )

    for attempt in range(1, retries + 1):
        try:
            result = await unitizer.run(prompt)
            by_id = {str(item.sentence_id): item for item in result.results}
            missing = [str(sentence_key(sentence)) for sentence in batch if str(sentence_key(sentence)) not in by_id]
            if missing:
                raise ValueError(f"Model response missing sentence_id values: {', '.join(missing[:5])}")
            return [by_id[str(sentence_key(sentence))] for sentence in batch]
        except Exception:
            if attempt == retries:
                raise
            await asyncio.sleep(2 ** attempt)

    raise RuntimeError("unreachable")


async def process_batch_with_fallback(
    unitizer: gpt.GPT,
    batch: list[dict],
    semaphore: asyncio.Semaphore,
) -> list[UnitizedSentence]:
    async with semaphore:
        try:
            return await unitize_batch(unitizer, batch)
        except Exception as batch_error:
            if len(batch) == 1:
                raise batch_error
            print(
                f"Batch failed with {len(batch)} sentences; retrying one sentence at a time. "
                f"Error: {batch_error}"
            )

    results: list[UnitizedSentence] = []
    for sentence in batch:
        async with semaphore:
            single_result = await unitize_batch(unitizer, [sentence])
            results.extend(single_result)
    return results


async def process_numbered_batch(
    unitizer: gpt.GPT,
    batch_index: int,
    batch: list[dict],
    semaphore: asyncio.Semaphore,
    *,
    batch_size: int,
    pending_total: int,
    batch_count: int,
) -> tuple[int, list[dict], list[UnitizedSentence]]:
    first = (batch_index - 1) * batch_size + 1
    last = min(batch_index * batch_size, pending_total)
    print(f"Processing batch {batch_index}/{batch_count} ({first}-{last}/{pending_total})")
    batch_results = await process_batch_with_fallback(unitizer, batch, semaphore)
    return batch_index, batch, batch_results


async def run_async(
    *,
    input_path: str,
    output_path: str,
    batch_size: int,
    max_concurrent_batches: int,
    checkpoint_every_batches: int,
    limit: int | None,
) -> None:
    data = util.read_json_file(input_path)
    filtered_sentences = [
        sentence
        for sentence in data["sentences"]
        if sentence.get("modality") != "undefined" and sentence.get("sentence")
    ]
    if limit is not None:
        filtered_sentences = filtered_sentences[:limit]

    processed = load_existing_results(output_path)
    pending_sentences = [
        sentence
        for sentence in filtered_sentences
        if str(sentence_key(sentence)) not in processed
    ]

    total = len(filtered_sentences)
    pending_total = len(pending_sentences)
    print(f"Total eligible sentences: {total}")
    print(f"Already processed: {len(processed)}")
    print(f"Pending: {pending_total}")

    if not pending_sentences:
        write_results(output_path, filtered_sentences, processed)
        print(f"No pending sentences. Output refreshed at {output_path}")
        return

    unitizer = build_unitizer()
    semaphore = asyncio.Semaphore(max_concurrent_batches)
    batches = list(chunks(pending_sentences, batch_size))
    tasks = [
        asyncio.create_task(
            process_numbered_batch(
                unitizer,
                batch_index,
                batch,
                semaphore,
                batch_size=batch_size,
                pending_total=pending_total,
                batch_count=len(batches),
            )
        )
        for batch_index, batch in enumerate(batches, start=1)
    ]

    completed_batches_since_checkpoint = 0
    for completed_task in asyncio.as_completed(tasks):
        batch_index, batch, batch_results = await completed_task
        for sentence, result in zip(batch, batch_results, strict=True):
            item = dict(sentence)
            item["units"] = result.units
            processed[str(sentence_key(sentence))] = item

        completed_batches_since_checkpoint += 1
        if completed_batches_since_checkpoint >= checkpoint_every_batches:
            write_results(output_path, filtered_sentences, processed)
            completed_batches_since_checkpoint = 0
            print(f"Checkpoint saved after batch {batch_index}: {len(processed)}/{total}")

    write_results(output_path, filtered_sentences, processed)
    print(f"Done. Wrote {len(processed)} processed sentences to {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unitize sentences in batches with OpenAI.")
    parser.add_argument("--input", default=os.getenv("UNITIZATION_INPUT", DEFAULT_INPUT_PATH))
    parser.add_argument("--output", default=os.getenv("UNITIZATION_OUTPUT", DEFAULT_OUTPUT_PATH))
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("UNITIZATION_BATCH_SIZE", DEFAULT_BATCH_SIZE)))
    parser.add_argument(
        "--max-concurrent-batches",
        type=int,
        default=int(os.getenv("UNITIZATION_MAX_CONCURRENT_BATCHES", DEFAULT_MAX_CONCURRENT_BATCHES)),
    )
    parser.add_argument(
        "--checkpoint-every-batches",
        type=int,
        default=int(os.getenv("UNITIZATION_CHECKPOINT_EVERY_BATCHES", DEFAULT_CHECKPOINT_EVERY_BATCHES)),
    )
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def run() -> None:
    args = parse_args()
    asyncio.run(
        run_async(
            input_path=args.input,
            output_path=args.output,
            batch_size=max(1, args.batch_size),
            max_concurrent_batches=max(1, args.max_concurrent_batches),
            checkpoint_every_batches=max(1, args.checkpoint_every_batches),
            limit=args.limit,
        )
    )
    

if __name__ == "__main__":
    run()
