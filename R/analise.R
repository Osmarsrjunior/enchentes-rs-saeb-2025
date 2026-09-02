required <- c("readxl", "dplyr", "tidyr", "stringi", "fixest", "MatchIt", "ggplot2", "readr")
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) stop("Instale os pacotes: ", paste(missing, collapse = ", "))

suppressPackageStartupMessages({
  library(readxl); library(dplyr); library(tidyr); library(stringi)
  library(fixest); library(MatchIt); library(ggplot2); library(readr)
})

root <- normalizePath(".")
hist_file <- file.path(root, "data_raw", "divulgacao_anos_finais_municipios_2023.xlsx")
saeb25_file <- file.path(root, "data_raw", "saeb_2025_brasil_estados_municipios_censitario.xlsx")
dir.create(file.path(root, "outputs", "tables"), recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(root, "outputs", "figures"), recursive = TRUE, showWarnings = FALSE)

norm_name <- function(x) {
  x |> stri_trans_general("Latin-ASCII") |> tolower() |>
    gsub("[^a-z0-9]+", " ", x = _) |> trimws()
}

treated_names <- c(
  "Bom Retiro do Sul","Lajeado","Vespasiano Corrêa","Estrela","Cruzeiro do Sul",
  "Taquari","Forquetinha","Alto Feliz","Araricá","Barão","Bom Princípio","Brochier",
  "Campo Bom","Capela de Santana","Dois Irmãos","Estância Velha","Harmonia","Ivoti",
  "Linha Nova","Montenegro","Morro Reuter","Nova Hartz","Novo Hamburgo","Pareci Novo",
  "Parobé","Poço das Antas","Portão","Presidente Lucena","Salvador do Sul",
  "Santa Maria do Herval","São José do Hortêncio","São José do Sul","São Leopoldo",
  "São Pedro da Serra","São Vendelino","Sapiranga","Taquara","Tupandi","Feliz",
  "Igrejinha","Butiá","Camaquã","Cerro Grande do Sul","Chuvisca","Dom Feliciano",
  "Minas do Leão","Sentinela do Sul","Sertão Santana","Caxias do Sul","Gramado",
  "Arroio do Tigre","Cachoeira do Sul","Estrela Velha","Novos Cabrais","Restinga Sêca",
  "Ibarama","Segredo","Dona Francisca","Paraíso do Sul","Agudo","Arroio Grande",
  "Capão do Leão","Pelotas","São Lourenço do Sul","Turuçu","Chuí","Rio Grande",
  "São José do Norte","Santa Vitória do Palmar","Porto Alegre","Canoas"
)

h <- read_excel(hist_file, skip = 9) |>
  filter(SG_UF == "RS", REDE == "Pública") |>
  mutate(code = as.integer(CO_MUNICIPIO), municipality = NO_MUNICIPIO)

years <- c(2007,2009,2011,2013,2015,2017,2019,2021,2023)
hist_long <- bind_rows(lapply(years, function(y) {
  bind_rows(
    transmute(h, code, municipality, year=y, subject="Matemática",
              score=as.numeric(.data[[paste0("VL_NOTA_MATEMATICA_", y)]])),
    transmute(h, code, municipality, year=y, subject="Língua Portuguesa",
              score=as.numeric(.data[[paste0("VL_NOTA_PORTUGUES_", y)]]))
  )
}))

s25 <- read_excel(saeb25_file, sheet = "Municípios") |>
  filter(CO_UF == 43,
         DEPENDENCIA_ADM == "Total - Federal, Estadual e Municipal",
         LOCALIZACAO == "Total")
saeb_long <- bind_rows(
  transmute(s25, code=as.integer(CO_MUNICIPIO), municipality=NO_MUNICIPIO,
            year=2025, subject="Matemática", score=as.numeric(MEDIA_9_MT)),
  transmute(s25, code=as.integer(CO_MUNICIPIO), municipality=NO_MUNICIPIO,
            year=2025, subject="Língua Portuguesa", score=as.numeric(MEDIA_9_LP))
)

panel <- bind_rows(hist_long, saeb_long) |>
  mutate(treated = as.integer(norm_name(municipality) %in% norm_name(treated_names)),
         post = as.integer(year == 2025), treat_post = treated * post)
write_csv(panel, file.path(root, "outputs", "painel_analitico_R.csv"))

# DiD transparente de duas ondas: Y_it = alpha_i + lambda_t + beta D_i*Post_t + erro_it.
twfe <- panel |> filter(year %in% c(2023, 2025), !is.na(score)) |>
  group_by(subject) |> group_modify(~{
    m <- feols(score ~ treat_post | code + year, cluster = ~code, data=.x)
    tibble(estimate=coef(m)["treat_post"], se=se(m)["treat_post"], p=pvalue(m)["treat_post"])
  })
write_csv(twfe, file.path(root, "outputs", "tables", "did_duas_ondas_R.csv"))

# Especificação principal: vizinho mais próximo nos níveis pré-tratamento e
# diferença pareada da mudança 2023–2025. Erro-padrão t entre pares.
matching <- panel |> filter(year %in% c(2017,2019,2023,2025)) |>
  select(code, municipality, treated, subject, year, score) |>
  pivot_wider(names_from=year, values_from=score) |>
  group_by(subject) |> group_modify(~{
    dat <- .x |> filter(complete.cases(`2017`, `2019`, `2023`, `2025`))
    mm <- matchit(treated ~ `2017` + `2019` + `2023`, data=dat,
                  method="nearest", distance="mahalanobis", replace=TRUE, ratio=1)
    md <- match.data(mm)
    tr <- md |> filter(treated == 1) |> arrange(subclass)
    co <- md |> filter(treated == 0) |> arrange(subclass)
    pair_delta <- (tr$`2025`-tr$`2023`) - (co$`2025`-co$`2023`)
    tibble(estimate=mean(pair_delta), se=sd(pair_delta)/sqrt(length(pair_delta)),
           p=2*pt(-abs(mean(pair_delta)/(sd(pair_delta)/sqrt(length(pair_delta)))),
                  df=length(pair_delta)-1), treated_n=length(pair_delta))
  })
write_csv(matching, file.path(root, "outputs", "tables", "matching_did_R.csv"))

means <- panel |> filter(year %in% c(2023,2025)) |>
  group_by(subject, treated, year) |> summarise(score=mean(score, na.rm=TRUE), .groups="drop") |>
  mutate(group=if_else(treated==1, "Retorno afetado", "Comparação"))

p <- ggplot(means, aes(year, score, color=group, linetype=subject)) +
  geom_line(linewidth=.8) + geom_point(size=2.2) +
  scale_x_continuous(breaks=c(2023,2025)) +
  labs(x="Ano", y="Proficiência média", color=NULL, linetype=NULL,
       title="Proficiência antes e depois das enchentes") +
  theme_minimal(base_size=11) + theme(legend.position="bottom")
ggsave(file.path(root,"outputs","figures","medias_2023_2025_R.png"),p,width=7.6,height=4.7,dpi=220)

message("Concluído. Consulte outputs/tables e outputs/figures.")
