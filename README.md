# Replicação — enchentes de 2024, vulnerabilidade e Saeb 2025

Este diretório reproduz as tabelas e figuras do artigo. A unidade de análise é
o município do Rio Grande do Sul; a exposição indica municípios citados no
panorama da Secretaria da Educação de 14 de maio de 2024 como tendo retorno
escolar afetado ou ainda em avaliação.

## Estrutura

- `R/analise.R`: análise principal em R.
- `data_raw/`: Saeb 2025, série histórica municipal do 9º ano e panorama oficial.
- `outputs/`: painel analítico, tabelas e figuras geradas pela execução validada.
- `analysis_pipeline.py`: implementação independente usada para conferir os resultados.

## Como executar

### Pipeline principal em Python

Requisitos: Python 3.12 ou superior.

```bash
python -m venv .venv
.venv\\Scripts\\activate
python -m pip install -r requirements.txt
python analysis_pipeline.py
python -m unittest discover -s tests -v
```

Em Linux ou macOS, use `source .venv/bin/activate` para ativar o ambiente.

### Verificação independente em R

1. Instale R 4.3 ou superior.
2. Abra este diretório como pasta de trabalho.
3. Execute `source("R/analise.R")`.

Pacotes necessários: `readxl`, `dplyr`, `tidyr`, `stringi`, `fixest`, `MatchIt`,
`ggplot2` e `readr`. O script para com uma mensagem clara se faltar algum pacote.

## Interpretação responsável

A DiD de duas ondas compara a mudança de 2023 a 2025 entre os grupos. Como o
estudo de evento revela diferenças anteriores de trajetória, a comparação sem
ajuste não deve ser lida isoladamente como causal. A especificação principal
pareia municípios em níveis de proficiência de 2017, 2019 e 2023 e então compara
a mudança 2023–2025. Mesmo assim, permanecem possíveis confundimento residual,
contaminação do grupo de comparação, migração, seleção de participação no Saeb e
mascaramento de perdas individuais pelas médias municipais.

## Proveniência

- Saeb 2025: arquivo censitário fornecido com o projeto, originalmente divulgado pelo Inep.
- Histórico até 2023: planilha municipal do Ideb/Saeb, cópia espelho do arquivo do Inep.
- Exposição: Secretaria da Educação do Rio Grande do Sul, panorama de 14/05/2024.

Os hashes SHA-256 dos dois arquivos de resultados educacionais constam em
`outputs/metadata.json`.

## Dados e privacidade

O pacote contém somente resultados educacionais públicos agregados por
município. Não há registros de estudantes ou escolas identificáveis. Os dados
originais permanecem sujeitos aos termos e à atribuição de suas fontes; a
licença MIT deste repositório aplica-se ao código e à documentação produzidos.

## Citação e licença

O código é disponibilizado sob licença MIT. Use `CITATION.cff` para citar o
repositório e atualize a referência do artigo ou o DOI quando disponíveis.

