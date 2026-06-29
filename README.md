# CRD13 New Version

Projeto CRD13 com frontend Angular, backend FastAPI/MCP e dados locais para busca, reescrita e analise de atestacoes.

## Dados e modelos

Os dados necessarios para carregar o projeto em outra maquina ficam versionados no repositorio. Arquivos grandes de dados, como indices SQLite e JSONs volumosos, sao rastreados com Git LFS.

Modelos de embeddings e caches locais nao entram no Git, porque podem ser baixados novamente pelas dependencias `sentence-transformers`/Hugging Face quando o backend inicializa.

Antes de clonar em outra maquina:

```bash
git lfs install
git clone git@github.com:ilexistools/crd13-new-version.git
cd crd13-new-version
git lfs pull
```

## Backend atual

```bash
cd new-backend
uv sync
uv run uvicorn app.main:app --reload
```

Crie um arquivo `.env` local quando precisar de chaves ou configuracoes privadas. Arquivos `.env` sao ignorados pelo Git.

## Frontend

```bash
cd frontend
npm install
npm start
```

## Backend legado/MCP

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python start_mcp.py
```
