# Registro de validação

Data: 2 de setembro de 2026.

## Verificações concluídas

- caminhos das fontes corrigidos para `data_raw/`;
- 2 arquivos Python compilados sem erro de sintaxe;
- `R/analise.R` analisado sem erro de sintaxe;
- hashes SHA-256 das duas planilhas educacionais conferidos;
- painel arquivado com 9.920 linhas e 496 municípios em 2025;
- apenas resultados municipais agregados, sem identificadores de estudantes ou escolas;
- estimativas DiD arquivadas conferidas: 2,0469329897 em Matemática e
  2,4120557914 em Língua Portuguesa;
- nenhum arquivo excede o limite de 100 MB do GitHub.

## Execução integral

A instalação local das bibliotecas Python não foi concluída porque o índice de
pacotes não respondeu nesta sessão. O workflow `.github/workflows/validate.yml`
instala as dependências em ambiente limpo, reexecuta `analysis_pipeline.py` e
roda os testes. O resultado desse workflow deve ser conferido após a publicação.

