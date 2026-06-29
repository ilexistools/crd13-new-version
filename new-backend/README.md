# CRD13 new backend

## Base SQLite de provisions

Para reconstruir a base SQLite a partir de `provisions.json`, sem gerar
embeddings nem usar extensões de busca vetorial, execute a partir desta pasta:

```powershell
python app/prepare/build_provisions_sqlite.py
```

O comando gera `app/assets/indexes/provisions.sqlite3`. A tabela
`provision_commodities` relaciona cada provision às suas commodities e possui
um índice na coluna `normalized_commodity`, apropriado para buscas exatas sem
diferenciar maiúsculas/minúsculas.

Para escolher arquivos diferentes:

```powershell
python app/prepare/build_provisions_sqlite.py --input caminho/provisions.json --db caminho/provisions.sqlite3
```

## Busca ranqueada de provisions

`ProvisionsSearchTool` filtra primeiro pelas commodities e então usa FTS5/BM25
sobre a sentença e as unidades de cada provision. O resultado já vem ordenado
por relevância e limitado a 20 itens por padrão; o índice textual é criado na
primeira busca e é recriado quando a base é reconstruída.

```python
from app.tools.provisions_search import ProvisionsSearchTool

results = ProvisionsSearchTool().run(
    commodities=["fish"],
    text="Fish products must be free from contamination.",
    limit=20,
)
```

Cada resultado inclui `rank`, `bm25_score` e `relevance`. `relevance` é uma
pontuação inteira de 0 a 100, normalizada em relação aos resultados da própria
busca; ela indica posição relativa, não probabilidade de aderência. Caso não
existam termos pesquisáveis ou correspondências textuais, a ferramenta retorna
até 20 provisions da commodity em ordem determinística como fallback, com
`bm25_score` e `relevance` iguais a `None`.

`run()` aplica então uma segunda filtragem por LLM e retorna somente os
registros escolhidos, preservando os mesmos campos de cada registro retornado
por `filter_results()`. Para obter apenas o ranking SQLite, sem a chamada ao
LLM, utilize `filter_results()` diretamente.

## Adequação de attestation

`AttestationRewriteTool` recebe uma attestation e as provisions já filtradas;
ele não realiza uma nova busca. A resposta informa se a redação foi alterada e
quais provisions fundamentaram a decisão.

```python
from app.tools.attestation_rewriter import AttestationRewriteTool

rewrite = AttestationRewriteTool().run(
    attestation="The meat has derived from animals reared in country/ zone which is free from foot-and-mouth disease.",
    provisions=filtered_provisions,
)
```

O retorno contém `original`, `rewritten`, `rewrite_applied`, `decision`,
`provisions_used` e `rewrite_notes`. `decision` é `rewritten`, `unchanged` ou
`insufficient_basis`; nos dois últimos casos, `rewritten` preserva a frase
original.
