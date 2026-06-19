# parlamento-data

Pipeline que transforma os snapshots de dados abertos da Assembleia da
República numa API estática servida via GitHub Pages.

## O que faz

1. Descarrega os ficheiros JSON publicados em
   [dadosabertos.parlamento.pt](https://www.parlamento.pt/Cidadania/Paginas/DadosAbertos.aspx).
2. Sanea tipos (datas, IDs, códigos) e parseia conteúdos com HTML embutido.
3. Divide os dados em ficheiros pequenos por entidade (uma iniciativa, um
   deputado, etc.), prontos para uma app móvel consumir incrementalmente.
4. Categoriza o estado de cada iniciativa para mostrar progressão na app.

## Estrutura do output

```
output/
├── meta.json
├── iniciativas/
│   ├── index.json        # lista resumida de todas as iniciativas
│   └── {iniId}.json      # detalhe de cada iniciativa
├── deputados/
│   ├── index.json
│   └── {idCadastro}.json
├── grupos-parlamentares/
│   └── index.json
└── comissoes/
    ├── index.json
    └── {orgId}.json
```

## Correr localmente

**Requisitos:** Python 3.9 ou superior. Em macOS, o Python 3.9 que vem com
o Xcode chega — mas se quiseres modernizar, `brew install python@3.12`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Primeira corrida — descarrega tudo (pode demorar ~30s pelos 60 MB do
# ficheiro de iniciativas).
python -m src.main

# Em desenvolvimento, evitar re-downloads:
python -m src.main --cache-max-age-hours 6
```

O output fica em `./output/`. Verifica `output/meta.json` para o resumo.

## Schema da API

Versão atual: `1`. Os ficheiros incluem o campo `schemaVersion` para
permitir migrações no futuro sem partir clientes antigos.

## Fontes de dados

Configuradas em `src/sources.py`. Os URLs da AR usam tokens encriptados
mas têm-se mostrado estáveis. Se algum deixar de funcionar:
1. Ir a https://www.parlamento.pt/Cidadania/Paginas/DadosAbertos.aspx
2. Navegar para a categoria correspondente
3. Clicar com o botão direito sobre o link JSON, "Copiar link"
4. Atualizar o URL em `sources.py`
