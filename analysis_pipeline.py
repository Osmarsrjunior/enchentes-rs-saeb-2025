"""Reproducible analysis for the RS 2024 floods and SAEB outcomes.

The main treatment is an operational educational disruption indicator: a
municipality appears in the RS Education Secretariat panorama of schools whose
return was delayed or still under evaluation on 14 May 2024.
"""
from pathlib import Path
import hashlib
import json
import re
import unicodedata

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.neighbors import NearestNeighbors
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data_raw"
OUT = ROOT / "outputs"
FIG = OUT / "figures"
TAB = OUT / "tables"
for d in (OUT, FIG, TAB):
    d.mkdir(parents=True, exist_ok=True)

HIST = RAW / "divulgacao_anos_finais_municipios_2023.xlsx"
SAEB25 = RAW / "saeb_2025_brasil_estados_municipios_censitario.xlsx"

TREATED_NAMES = [
    "Bom Retiro do Sul", "Lajeado", "Vespasiano Corrêa", "Estrela",
    "Cruzeiro do Sul", "Taquari", "Forquetinha", "Alto Feliz", "Araricá",
    "Barão", "Bom Princípio", "Brochier", "Campo Bom", "Capela de Santana",
    "Dois Irmãos", "Estância Velha", "Harmonia", "Ivoti", "Linha Nova",
    "Montenegro", "Morro Reuter", "Nova Hartz", "Novo Hamburgo", "Pareci Novo",
    "Parobé", "Poço das Antas", "Portão", "Presidente Lucena", "Salvador do Sul",
    "Santa Maria do Herval", "São José do Hortêncio", "São José do Sul",
    "São Leopoldo", "São Pedro da Serra", "São Vendelino", "Sapiranga", "Taquara",
    "Tupandi", "Feliz", "Igrejinha", "Butiá", "Camaquã", "Cerro Grande do Sul",
    "Chuvisca", "Dom Feliciano", "Minas do Leão", "Sentinela do Sul",
    "Sertão Santana", "Caxias do Sul", "Gramado", "Arroio do Tigre",
    "Cachoeira do Sul", "Estrela Velha", "Novos Cabrais", "Restinga Sêca",
    "Ibarama", "Segredo", "Dona Francisca", "Paraíso do Sul", "Agudo",
    "Arroio Grande", "Capão do Leão", "Pelotas", "São Lourenço do Sul", "Turuçu",
    "Chuí", "Rio Grande", "São José do Norte", "Santa Vitória do Palmar",
    "Porto Alegre", "Canoas",
]

def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()

def load_panel():
    h = pd.read_excel(HIST, header=9)
    h = h[(h.SG_UF == "RS") & (h.REDE == "Pública")].copy()
    h["code"] = pd.to_numeric(h.CO_MUNICIPIO, errors="coerce").astype("Int64")
    h["municipality"] = h.NO_MUNICIPIO.astype(str)
    rows = []
    for year in [2007, 2009, 2011, 2013, 2015, 2017, 2019, 2021, 2023]:
        for subject, col in [("Matemática", f"VL_NOTA_MATEMATICA_{year}"),
                             ("Língua Portuguesa", f"VL_NOTA_PORTUGUES_{year}")]:
            tmp = h[["code", "municipality", col]].rename(columns={col: "score"})
            tmp["year"], tmp["subject"] = year, subject
            rows.append(tmp)

    s25 = pd.read_excel(SAEB25, sheet_name="Municípios")
    s25 = s25[(s25.CO_UF == 43) &
              (s25.DEPENDENCIA_ADM == "Total - Federal, Estadual e Municipal") &
              (s25.LOCALIZACAO == "Total")].copy()
    for subject, col in [("Matemática", "MEDIA_9_MT"),
                         ("Língua Portuguesa", "MEDIA_9_LP")]:
        tmp = s25[["CO_MUNICIPIO", "NO_MUNICIPIO", col]].rename(
            columns={"CO_MUNICIPIO": "code", "NO_MUNICIPIO": "municipality", col: "score"})
        tmp["code"] = pd.to_numeric(tmp.code, errors="coerce").astype("Int64")
        tmp["year"], tmp["subject"] = 2025, subject
        rows.append(tmp)
    panel = pd.concat(rows, ignore_index=True)
    panel["score"] = pd.to_numeric(panel["score"], errors="coerce")
    treated_norm = {norm(x) for x in TREATED_NAMES}
    panel["treated"] = panel.municipality.map(norm).isin(treated_norm).astype(int)
    panel["post"] = (panel.year == 2025).astype(int)
    panel["treat_post"] = panel.treated * panel.post
    base = (panel[panel.year.isin([2017, 2019])]
            .groupby("code", as_index=False).score.mean().rename(columns={"score":"baseline_score"}))
    panel = panel.merge(base, on="code", how="left")
    cut = panel[["code","baseline_score"]].drop_duplicates().baseline_score.quantile(1/3)
    panel["low_baseline"] = (panel.baseline_score <= cut).astype(int)
    panel["triple"] = panel.treat_post * panel.low_baseline
    return panel

def ols_cluster(y, X, clusters):
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    ok = np.isfinite(y) & np.isfinite(X).all(axis=1)
    y, X, clusters = y[ok], X[ok], np.asarray(clusters)[ok]
    inv = np.linalg.pinv(X.T @ X)
    b = inv @ X.T @ y
    u = y - X @ b
    meat = np.zeros((X.shape[1], X.shape[1]))
    unique = pd.unique(clusters)
    for g in unique:
        z = X[clusters == g].T @ u[clusters == g]
        meat += np.outer(z, z)
    G, N, K = len(unique), len(y), X.shape[1]
    correction = (G/(G-1))*((N-1)/(N-K)) if G > 1 and N > K else 1
    V = correction * inv @ meat @ inv
    se = np.sqrt(np.maximum(np.diag(V), 0))
    t = b / se
    p = 2 * stats.t.sf(np.abs(t), max(G-1, 1))
    return b, se, p, len(y), G

def design_twfe(df, variable="treat_post", years=None, extra=None):
    d = df.copy()
    if years is not None:
        d = d[d.year.isin(years)]
    d = d.dropna(subset=["score", variable, "code", "year"])
    parts = [np.ones((len(d), 1)), d[[variable]].to_numpy(float)]
    names = ["Intercept", variable]
    if extra:
        for e in extra:
            parts.append(d[[e]].to_numpy(float)); names.append(e)
    muni = pd.get_dummies(d.code.astype(str), drop_first=True, dtype=float)
    yr = pd.get_dummies(d.year.astype(str), drop_first=True, dtype=float)
    parts += [muni.to_numpy(), yr.to_numpy()]
    names += list("muni_" + muni.columns) + list("year_" + yr.columns)
    X = np.column_stack(parts)
    b,se,p,n,g = ols_cluster(d.score, X, d.code)
    return {name:{"estimate":b[i],"se":se[i],"p":p[i]} for i,name in enumerate(names)}, n, g

def event_study(df, subject):
    # 2015 is omitted because the historical municipal workbook contains a
    # discontinuity in coverage that is not comparable with adjacent waves.
    d = df[(df.subject == subject) & df.year.isin([2007,2009,2011,2013,2017,2019,2021,2023,2025])].copy()
    event_years = [2007,2009,2011,2013,2017,2019,2021,2025]
    for y in event_years:
        d[f"event_{y}"] = d.treated * (d.year == y)
    d = d.dropna(subset=["score"])
    variables = [f"event_{y}" for y in event_years]
    parts=[np.ones((len(d),1)), d[variables].to_numpy(float)]
    names=["Intercept"]+variables
    muni=pd.get_dummies(d.code.astype(str),drop_first=True,dtype=float)
    yr=pd.get_dummies(d.year.astype(str),drop_first=True,dtype=float)
    X=np.column_stack(parts+[muni.to_numpy(),yr.to_numpy()])
    b,se,p,n,g=ols_cluster(d.score,X,d.code)
    out=[]
    for i,y in enumerate(event_years, start=1):
        out.append({"subject":subject,"year":y,"estimate":b[i],"se":se[i],"p":p[i]})
    out.append({"subject":subject,"year":2023,"estimate":0,"se":0,"p":np.nan})
    return pd.DataFrame(out).sort_values("year")

def main():
    panel = load_panel()
    coverage = panel[panel.year.eq(2025)].groupby("subject").agg(
        municipalities=("code","nunique"), treated=("treated","sum"), missing=("score",lambda x:x.isna().sum()))
    results=[]
    for subject in ["Matemática","Língua Portuguesa"]:
        d=panel[panel.subject.eq(subject)]
        for label,years in [("Principal: DiD 2023-2025",[2023,2025]),
                            ("Múltiplos pré-períodos sem 2021",[2017,2019,2023,2025]),
                            ("Com 2021",[2017,2019,2021,2023,2025]),
                            ("Painel longo",None)]:
            res,n,g=design_twfe(d,years=years)
            q=res["treat_post"]
            results.append({"subject":subject,"model":label,"estimate":q["estimate"],"se":q["se"],"p":q["p"],"n":n,"clusters":g})
        res,n,g=design_twfe(d,years=[2023,2025],extra=["triple"])
        for term in ["treat_post","triple"]:
            q=res[term]
            results.append({"subject":subject,"model":"Heterogeneidade: "+term,"estimate":q["estimate"],"se":q["se"],"p":q["p"],"n":n,"clusters":g})
    results=pd.DataFrame(results)
    events=pd.concat([event_study(panel,s) for s in ["Matemática","Língua Portuguesa"]])

    # Raw two-period group means for transparent interpretation.
    means=(panel[panel.year.isin([2023,2025])]
           .groupby(["subject","treated","year"],as_index=False).score.mean())
    means["group"]=means.treated.map({0:"Controle",1:"Retorno escolar afetado"})
    pivot=means.pivot_table(index=["subject","group"],columns="year",values="score").reset_index()
    pivot["change"]=pivot[2025]-pivot[2023]

    panel.to_csv(OUT/"painel_analitico.csv",index=False)
    results.to_csv(TAB/"resultados_modelos.csv",index=False)
    events.to_csv(TAB/"estudo_evento.csv",index=False)
    pivot.to_csv(TAB/"medias_grupos.csv",index=False)
    coverage.to_csv(TAB/"cobertura.csv")

    # Nearest-neighbour ATT on the 2023-2025 change, matched on three pre-period scores.
    matched=[]
    for subject in ["Matemática","Língua Portuguesa"]:
        wide=(panel[panel.subject.eq(subject)].pivot_table(index=["code","municipality","treated"],columns="year",values="score").reset_index())
        use=wide.dropna(subset=[2017,2019,2023,2025]).copy()
        tr=use[use.treated.eq(1)].copy(); co=use[use.treated.eq(0)].copy()
        features=[2017,2019,2023]
        mu=use[features].mean(); sd=use[features].std(ddof=0).replace(0,1)
        nn=NearestNeighbors(n_neighbors=1).fit((co[features]-mu)/sd)
        _,idx=nn.kneighbors((tr[features]-mu)/sd)
        tr_change=(tr[2025]-tr[2023]).to_numpy()
        co_change=(co.iloc[idx[:,0]][2025].to_numpy()-co.iloc[idx[:,0]][2023].to_numpy())
        dif=tr_change-co_change
        est=float(dif.mean()); se=float(dif.std(ddof=1)/np.sqrt(len(dif)))
        matched.append({"subject":subject,"estimate":est,"se":se,"p":float(2*stats.t.sf(abs(est/se),len(dif)-1)),"treated_n":len(dif),"unique_controls":int(co.iloc[idx[:,0]].code.nunique())})
    pd.DataFrame(matched).to_csv(TAB/"matching_robustez.csv",index=False)

    # Childhood outcome (5th grade) is available for 2025. Without the matching
    # historical early-years file, this is explicitly descriptive, not causal.
    s25 = pd.read_excel(SAEB25, sheet_name="Municípios")
    s25 = s25[(s25.CO_UF == 43) &
              (s25.DEPENDENCIA_ADM == "Total - Federal, Estadual e Municipal") &
              (s25.LOCALIZACAO == "Total")].copy()
    s25["treated"] = s25.NO_MUNICIPIO.map(norm).isin({norm(x) for x in TREATED_NAMES}).astype(int)
    child=[]
    for subject,col in [("Matemática","MEDIA_5_MT"),("Língua Portuguesa","MEDIA_5_LP")]:
        a=pd.to_numeric(s25.loc[s25.treated.eq(1),col],errors="coerce").dropna()
        b=pd.to_numeric(s25.loc[s25.treated.eq(0),col],errors="coerce").dropna()
        test=stats.ttest_ind(a,b,equal_var=False)
        child.append({"subject":subject,"treated_mean":a.mean(),"control_mean":b.mean(),
                      "difference":a.mean()-b.mean(),"p_welch":test.pvalue,
                      "treated_n":len(a),"control_n":len(b)})
    pd.DataFrame(child).to_csv(TAB/"quinto_ano_descritivo_2025.csv",index=False)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig,ax=plt.subplots(figsize=(8.2,4.8))
    for subject,color,marker in [("Matemática","#9C3D2E","o"),("Língua Portuguesa","#244C66","s")]:
        e=events[events.subject.eq(subject)]
        ax.errorbar(e.year,e.estimate,yerr=1.96*e.se,label=subject,color=color,marker=marker,capsize=3)
    ax.axhline(0,color="black",lw=.8); ax.axvline(2024,color="#777",ls="--",lw=1)
    ax.set(xlabel="Ano do Saeb",ylabel="Diferença em relação a 2023 (pontos)",title="Estudo de evento: municípios com retorno escolar afetado")
    ax.legend(frameon=False); fig.tight_layout(); fig.savefig(FIG/"figura_estudo_evento.png",dpi=220); plt.close(fig)

    fig,ax=plt.subplots(figsize=(7.6,4.7))
    plot=means.copy()
    for (subject,group),g in plot.groupby(["subject","group"]):
        ls="-" if subject=="Matemática" else "--"
        color="#9C3D2E" if group=="Retorno escolar afetado" else "#244C66"
        ax.plot(g.year,g.score,marker="o",ls=ls,color=color,label=f"{group} — {subject}")
    ax.set(xlabel="Ano",ylabel="Proficiência média",title="Proficiência antes e depois das enchentes")
    ax.legend(fontsize=8,frameon=False); fig.tight_layout(); fig.savefig(FIG/"figura_medias_2023_2025.png",dpi=220); plt.close(fig)

    metadata={"sha256_historical":sha256(HIST),"sha256_saeb_2025":sha256(SAEB25),
              "treated_names":sorted(TREATED_NAMES),"n_treated_names":len(set(map(norm,TREATED_NAMES))),
              "coverage":coverage.reset_index().to_dict(orient="records")}
    (OUT/"metadata.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    print(results.to_string(index=False))
    print("\nMEANS\n",pivot.to_string(index=False))
    print("\nCOVERAGE\n",coverage.to_string())

if __name__ == "__main__":
    main()
