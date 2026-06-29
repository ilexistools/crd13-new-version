Em prepare, crie um script para ler os arquivos em raw/new_organization e criar um arquivo com as informações de sentenças.

Exemplo de informações que deve conter:

{
    sentences:[
        {

    "document_id":"",
    "type":"",
    "commodities": [],
    "section_title": "",
    "page_start":0,
    "page_end":0,
    "sentence": "",
    "category": "",
    "modality": "",
    "function": "",

        }
    ]

}

 Salve o arquivo sentences.json em assets/resources.


Em prepare, crie um script para ler os arquivos em raw/new_organization e criar um arquivo com as informações de todos os documentos. 
Exemplo:

{
    [
  "document": {
    "id": "bace4444-ce76-4286-ba3a-702a3303e203",
    "type": "CODEX",
    "document_type": "Standards",
    "reference": "CXS 206-1999",
    "year": "1999",
    "title": "General Standard for the Use of Dairy Terms",
    "label": "CXS 206-1999 - General Standard for the Use of Dairy Terms",
    "committee": "CCMMP",
    "last_modified": "2022",
    "url": "https://www.fao.org/fao-who-codexalimentarius/sh-proxy/en/?lnk=1&url=https%253A%252F%252Fworkspace.fao.org%252Fsites%252Fcodex%252FStandards%252FCXS%2B206-1999%252FCXS_206e.pdf",
    "processes": [
      "Labelling and Consumer Information",
      "Product Standards"
    ],
    "commodities": [
    {
      "name": "dairy",
      "terms": [
        "milk",
        "milk product",
        "composite milk product",
        "dairy term",
        "raw milk",
        "reconstituted milk product",
        "recombined milk product",
        "milkfat",
        "milk-solids-non-fat"
      ],
      "sources": {
        "documents_info": true,
        "commodities_index": true
      }
    }
  ],
  "sections":[
    "section_title": "",
    "section_page_start": 1,
    "section_page_end": 1
  ]

    ]
  }

  Salve o arquivo documents.json em aseets/resources.
  