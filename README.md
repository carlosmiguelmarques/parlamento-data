# parlamento-data

API estática que serve os dados abertos da Assembleia da República num
formato pronto a consumir por apps móveis. Atualizada diariamente via
GitHub Actions e servida via GitHub Pages — sem servidor, sem custos.

**URL base:** https://carlosmiguelmarques.github.io/parlamento-data

## O que faz

1. Descarrega os snapshots de dados abertos publicados em
   [dadosabertos.parlamento.pt](https://www.parlamento.pt/Cidadania/Paginas/DadosAbertos.aspx).
2. Sanea tipos (datas, IDs, códigos), parseia HTML embutido nas votações,
   classifica o estado atual de cada iniciativa.
3. Divide tudo em ficheiros pequenos por entidade (uma iniciativa, um
   deputado, etc.), prontos para uma app móvel descarregar incrementalmente.

## Endpoints

Todos os endpoints servem JSON sobre HTTPS, com cache do GitHub Pages.

### Metadados

| Endpoint | Descrição |
|---|---|
| [`/meta.json`](https://carlosmiguelmarques.github.io/parlamento-data/meta.json) | Versão do schema, timestamp da geração, contagens |

### Iniciativas

| Endpoint | Descrição |
|---|---|
| [`/iniciativas/index.json`](https://carlosmiguelmarques.github.io/parlamento-data/iniciativas/index.json) | Lista resumida de todas as iniciativas (id, tipo, autores, estado atual) |
| `/iniciativas/{iniId}.json` | Detalhe completo de uma iniciativa (timeline, votações, links) |

Exemplo: o [Orçamento do Estado para 2026](https://carlosmiguelmarques.github.io/parlamento-data/iniciativas/315671.json) (`iniId=315671`).

### Deputados

| Endpoint | Descrição |
|---|---|
| [`/deputados/index.json`](https://carlosmiguelmarques.github.io/parlamento-data/deputados/index.json) | Lista resumida de todos os deputados (id, nome, GP, círculo, ativo) |
| `/deputados/{idCadastro}.json` | Detalhe de um deputado, com histórico de mandatos e GPs |

### Grupos parlamentares

| Endpoint | Descrição |
|---|---|
| [`/grupos-parlamentares/index.json`](https://carlosmiguelmarques.github.io/parlamento-data/grupos-parlamentares/index.json) | Lista de GPs com contagem de deputados efetivos |

### Comissões

| Endpoint | Descrição |
|---|---|
| [`/comissoes/index.json`](https://carlosmiguelmarques.github.io/parlamento-data/comissoes/index.json) | Lista das comissões parlamentares |
| `/comissoes/{orgId}.json` | Detalhe de uma comissão com a sua composição |

## Schema versioning

Todos os ficheiros incluem o campo `schemaVersion`. Versão atual: `1`.
Mudanças que quebrem clientes vão incrementar este número e estar
documentadas no `CHANGELOG`.

## Categorias de estado

Cada iniciativa tem um campo `estado.categoria` com uma de oito categorias
agregadas a partir dos 65 códigos de fase originais da AR:

- `entrada` — recém-entrada, ainda não distribuída
- `em_apreciacao` — em comissões, audições, especialidade
- `votacao_generalidade` — em votação na generalidade
- `aprovada_generalidade` — aprovada na generalidade
- `votacao_final` — em votação final
- `aprovada` — entre aprovação e publicação (decreto, promulgação)
- `publicada` — lei ou resolução publicada
- `vetada` — vetada pelo Presidente
- `retirada` — retirada pelo autor
- `rejeitada` — não admitida
- `caducada` — caducou no fim de legislatura

## Frequência de atualização

O GitHub Actions corre o pipeline diariamente às 06:00 UTC (07:00 hora
de Lisboa). Pode também ser corrido manualmente em Actions → "Atualizar
dados da AR" → Run workflow.

## Correr localmente

**Requisitos:** Python 3.10+ (necessário para o `truststore`, que resolve
problemas de cadeia de certificados com servidores `.gov.pt`).

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m src.main
```

O output fica em `./output/`. Para evitar re-downloads em desenvolvimento:

```bash
python -m src.main --cache-max-age-hours 6
```

## Estrutura do projeto

```
parlamento-data/
├── src/
│   ├── sources.py        # URLs dos snapshots da AR
│   ├── fetch.py          # downloads
│   ├── transform.py      # transformação principal
│   ├── categorias.py     # mapa código de fase → categoria
│   └── main.py           # orquestrador
├── .github/workflows/
│   └── update-data.yml   # cron + deploy para Pages
└── requirements.txt
```

## Atribuição dos dados

Os dados servidos por estes endpoints derivam dos
[Dados Abertos da Assembleia da República](https://www.parlamento.pt/Cidadania/Paginas/DadosAbertos.aspx).
Esses dados são propriedade da AR e o seu uso está sujeito aos termos
definidos pelo Parlamento — não pela licença deste repositório.

Ao usar estes endpoints, faz atribuição à Assembleia da República como
fonte original dos dados.

## Licença

O **código** deste repositório (scripts Python, workflows, schema) está
licenciado sob a [Licença MIT](LICENSE).

Os **dados** servidos pelos endpoints provêm da Assembleia da República
e seguem as condições aplicáveis aos dados abertos do Parlamento (ver
secção anterior).

## Como atualizar fontes

Os URLs da AR usam tokens encriptados no parâmetro `path`. Têm-se mostrado
estáveis, mas se algum dia deixarem de funcionar, o workflow vai falhar
e mandar um email automático. Resolução:

1. Ir a https://www.parlamento.pt/Cidadania/Paginas/DadosAbertos.aspx
2. Navegar para a categoria correspondente
3. Copiar o novo URL JSON da legislatura XVII
4. Atualizar `src/sources.py` e fazer push
