from pathlib import Path
from typing import Optional
import re
import yaml



DEFAULT_INSTRUCTION_FOLDER = Path(__file__).resolve().parents[1] / "assets" / "instructions"
DEFAULT_AGENTS_FOLDER = Path(__file__).resolve().parents[1] / "assets" / "agents"


def load_agent_markdown(agent_id: str) -> dict:
    """
    Carrega um arquivo .md de definição de agente e retorna um dicionário.

    Espera um formato como:

    ---
    id: translator
    role: Portuguese Translator
    goal: ...
    max_tokens: 2048
    model: gpt-4.1-mini
    ---

    # INPUT
    ...

    # OUTPUT
    ...

    # INSTRUCTIONS
    ...

    # KNOWLEDGE
    ...
    """

    file_path = Path(DEFAULT_AGENTS_FOLDER) / f"{agent_id}.md"

    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    content = file_path.read_text(encoding="utf-8")

    data = {
        "metadata": {},
        "sections": {}
    }

    # Extrai o frontmatter YAML
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", content, re.DOTALL)

    if frontmatter_match:
        frontmatter_text = frontmatter_match.group(1)
        data["metadata"] = yaml.safe_load(frontmatter_text) or {}
        body = content[frontmatter_match.end():]
    else:
        body = content

    # Extrai seções Markdown de nível 1: # INPUT, # OUTPUT etc.
    section_pattern = re.compile(
        r"^#\s+(.+?)\s*$",
        re.MULTILINE
    )

    matches = list(section_pattern.finditer(body))

    for i, match in enumerate(matches):
        section_name = match.group(1).strip().lower()

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)

        section_content = body[start:end].strip()

        data["sections"][section_name] = section_content

    return data


def load_agent_config(agent_id: str, fallback_model: str = "") -> dict:
    agent_data = load_agent_markdown(agent_id)
    metadata = agent_data["metadata"]

    instructions_parts = [
        metadata.get("goal", ""),
        metadata.get("backstory", ""),
        *agent_data["sections"].values(),
    ]
    instructions = "\n\n".join(part for part in instructions_parts if part)

    return {
        "name": metadata.get("name", agent_id),
        "role": metadata.get("role", "You are a helpful assistant."),
        "instructions": instructions,
        "model": metadata.get("model") or fallback_model,
        "max_tokens": int(metadata.get("max_tokens", 2048)),
    }


def instruction_loader(
    instruction_id: str,
    instruction_folder: str | Path = DEFAULT_INSTRUCTION_FOLDER,
    encoding: str = "utf-8",
    default: Optional[str] = None,
) -> str:
    """
    Load instructions from a file.

    Args:
        instruction_id (str): The ID of the instruction to load.
        instruction_folder (str): Folder where instruction files are stored.
        encoding (str): File encoding.
        default (Optional[str]): Default value if file is not found.

    Returns:
        str: The instructions loaded from the file.

    Raises:
        FileNotFoundError: If file does not exist and no default is provided.
    """
    instruction_file = Path(instruction_folder) / f"{instruction_id}.md"

    if not instruction_file.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"Instruction file not found: {instruction_file}")

    with instruction_file.open("r", encoding=encoding) as file:
        return file.read().strip()


