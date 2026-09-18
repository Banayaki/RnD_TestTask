import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def _():
    from dataclasses import fields
    from pathlib import Path
    import sys
    import traceback

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    import marimo as mo
    import matplotlib.pyplot as plt
    import pandas as pd
    import seaborn as sns

    from rnd_test_task.model import Client, CommType, Communication
    from rnd_test_task.service import ClientCommSimpleService
    from rnd_test_task.settings import settings
    from rnd_test_task.tools import CsvSanitizer

    return (
        Client,
        ClientCommSimpleService,
        CommType,
        Communication,
        CsvSanitizer,
        fields,
        mo,
        pd,
        plt,
        project_root,
        settings,
        sns,
        traceback,
    )


@app.cell
def _(mo):
    mo.md("""
    # Исследование базы коммуникаций
    """)
    return


@app.cell
def _(Client, Communication, CsvSanitizer, project_root, settings, traceback):
    sanitizer = CsvSanitizer()
    clients_result = sanitizer.read_and_sanitize(
        project_root / settings.clients_path, Client
    )
    communications_result = sanitizer.read_and_sanitize(
        project_root / settings.communications_path, Communication
    )
    issues = clients_result.errors + communications_result.errors
    if issues:
        details = "\n".join(
            "".join(traceback.format_exception(issue)) for issue in issues
        )
        raise RuntimeError(details)

    clients = clients_result.data
    communications = communications_result.data
    return clients, clients_result, communications, communications_result


@app.cell
def _(clients_result, communications_result, mo):
    warnings = clients_result.warnings + communications_result.warnings
    if warnings:
        mo.callout(
            "\n".join(str(warning) for warning in warnings),
            kind="warn",
        )
    return


@app.cell
def _(
    Client,
    ClientCommSimpleService,
    CommType,
    clients,
    communications,
    fields,
    pd,
    settings,
):
    service = ClientCommSimpleService()
    rows = []
    for comm_type in CommType:
        for _, client_row in clients.iterrows():
            profile = Client(
                **{field.name: client_row[field.name] for field in fields(Client)}
            )
            history = communications.loc[
                communications["client_pin"] == profile.client_pin
            ]
            prediction = service.score(
                profile=profile,
                comm_type=comm_type,
                comm_history=history,
                clients_db=clients,
                comm_db=communications,
                runtime_settings=settings,
                **settings.score_kwargs,
            )
            rows.append(
                {
                    "comm_type": comm_type.value,
                    "verdict": prediction.verdict,
                    "p": prediction.score,
                }
            )

    predictions = pd.DataFrame(rows)
    return (predictions,)


@app.cell
def _(predictions):
    predictions.head()
    return


@app.cell
def _(predictions):
    verdict_order = ["Подходит", "Спорно", "Не подходит", "Мало данных"]
    verdict_counts = (
        predictions.groupby(["comm_type", "verdict"], observed=True)
        .size()
        .rename("client_count")
        .reset_index()
    )
    verdict_summary = (
        verdict_counts.pivot(
            index="comm_type", columns="verdict", values="client_count"
        )
        .reindex(columns=verdict_order, fill_value=0)
        .fillna(0)
        .astype(int)
    )
    return verdict_counts, verdict_order, verdict_summary


@app.cell
def _(mo, verdict_summary):
    mo.md("## Число клиентов по каждому вердикту")
    mo.ui.table(verdict_summary.reset_index(), pagination=False)
    return


@app.cell
def _(plt, sns, verdict_counts, verdict_order):
    figure, axis = plt.subplots(figsize=(12, 6))
    sns.barplot(
        data=verdict_counts,
        x="comm_type",
        y="client_count",
        hue="verdict",
        hue_order=verdict_order,
        ax=axis,
    )
    axis.set(
        title="Распределение вердиктов по типам коммуникаций",
        xlabel="Тип коммуникации",
        ylabel="Число клиентов",
    )
    axis.tick_params(axis="x", rotation=25)
    figure.tight_layout()
    return (figure,)


@app.cell
def _(figure):
    figure
    return


@app.cell
def _(plt, sns, verdict_summary):
    figure_heatmap, axis_heatmap = plt.subplots(figsize=(9, 5))
    sns.heatmap(
        verdict_summary,
        annot=True,
        fmt="d",
        cmap="Blues",
        cbar_kws={"label": "Число клиентов"},
        ax=axis_heatmap,
    )
    axis_heatmap.set(
        title="Матрица количества клиентов по вердиктам",
        xlabel="Вердикт",
        ylabel="Тип коммуникации",
    )
    figure_heatmap.tight_layout()
    return (figure_heatmap,)


@app.cell
def _(figure_heatmap):
    figure_heatmap
    return


@app.cell
def _(figure, figure_heatmap):
    figure.savefig("./notebooks/hist.png")
    figure_heatmap.savefig("./notebooks/heatmap.png")
    return


@app.cell
def _(verdict_summary):
    verdict_summary.reset_index().to_markdown("./notebooks/table.md")
    return


@app.cell
def _(communications):
    comms_count = (
        communications.groupby(["client_pin"], observed=True)
        .size()
        .reset_index()
    )
    comms_count
    return


@app.cell
def _(verdict_summary):
    verdict_summary
    return


@app.cell
def _(communications):
    communication_success = (
        communications.groupby("comm_type", observed=True)["success"]
        .agg(communication_count="count", success_count="sum", success_rate="mean")
        .reset_index()
        .sort_values("success_rate", ascending=False)
    )
    return (communication_success,)


@app.cell
def _(communication_success, mo):
    mo.md("## Относительная успешность коммуникаций")
    mo.ui.table(communication_success, pagination=False)
    return


@app.cell
def _(communication_success, plt, sns):
    figure_success, axis_success = plt.subplots(figsize=(10, 5))
    sns.barplot(
        data=communication_success,
        x="comm_type",
        y="success_rate",
        ax=axis_success,
    )
    axis_success.set(
        title="Доля успешных коммуникаций по типам",
        xlabel="Тип коммуникации",
        ylabel="Доля success = 1",
        ylim=(0, 1),
    )
    axis_success.tick_params(axis="x", rotation=25)
    figure_success.tight_layout()
    return (figure_success,)


@app.cell
def _(figure_success):
    figure_success
    return


@app.cell
def _(figure_success):
    figure_success.savefig("./notebooks/different_types_success_rate.png")
    return


@app.cell
def _(communication_success):
    communication_success.reset_index().to_markdown("./notebooks/table_types_success_rate.md")
    return


@app.cell
def _(communications, pd):
    communications["comm_date"] = pd.to_datetime(communications["comm_date"], errors="coerce")

    start_date = pd.Timestamp("2026-08-31")
    end_date = pd.Timestamp("2026-09-14")

    # Берём только коммуникации внутри fatigue-окна
    recent = communications[
        communications["comm_date"].between(start_date, end_date, inclusive="both")
    ].copy()

    # Ищем пары (client_pin, comm_type), у которых:
    # 1) была хотя бы одна коммуникация в окне
    # 2) все коммуникации этого типа в окне успешные
    result = (
        recent.groupby(["client_pin", "comm_type"], as_index=False)
        .agg(
            last_comm_date=("comm_date", "max"),
            n_comms=("success", "size"),
            n_success=("success", "sum"),
        )
    )

    result = result[result["n_success"] == result["n_comms"]]
    result
    return


@app.cell
def _(communications):
    communications.sort_values("comm_date", ascending=False)
    return


@app.cell
def _(communications):
    communications.groupby("client_pin").agg(
        n_success=("success", "sum"),
        n_total=("success", "count")
    ).sort_values("n_success")
    return


@app.cell
def _():
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
