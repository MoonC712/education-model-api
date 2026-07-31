from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from education_model.interventions import (
    SimulationOptions,
    list_interventions,
    simulate_intervention,
    vector_change_statuses,
)
from education_model.project_paths import ProjectPaths
from education_model.visualization import (
    DIMENSIONS,
    DIMENSION_LABELS,
    archetypes_wide,
    compute_population_embedding,
    group_display,
    load_project_data,
    profile_indicator_table,
)


st.set_page_config(
    page_title="EduBridge",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner=False)
def get_project_data(root: str):
    return load_project_data(ProjectPaths.from_root(Path(root)))


def radar_figure(vector: dict[str, float | None], title: str):
    categories = [DIMENSION_LABELS[d] for d in DIMENSIONS]
    values = [vector.get(d) for d in DIMENSIONS]
    safe_values = [0.0 if value is None or pd.isna(value) else float(value) for value in values]
    figure = go.Figure()
    figure.add_trace(
        go.Scatterpolar(
            r=safe_values + [safe_values[0]],
            theta=categories + [categories[0]],
            fill="toself",
            name=title,
        )
    )
    figure.update_layout(
        title=title,
        polar={"radialaxis": {"visible": True, "range": [0, 100]}},
        margin={"l": 30, "r": 30, "t": 70, "b": 30},
        height=470,
        showlegend=False,
    )
    return figure


def vector_bar(vector: dict[str, float | None], title: str):
    frame = pd.DataFrame(
        {
            "dimension": [DIMENSION_LABELS[d] for d in DIMENSIONS],
            "score": [vector.get(d) for d in DIMENSIONS],
        }
    )
    figure = px.bar(frame, x="score", y="dimension", orientation="h", text_auto=".2f", title=title)
    figure.update_xaxes(range=[0, 100], title="Korea-relative percentile")
    figure.update_yaxes(title=None)
    figure.update_layout(height=400)
    return figure


def select_profile(frame: pd.DataFrame, key_prefix: str) -> pd.Series:
    group_options = ["All assigned groups"] + sorted(
        frame.loc[frame["ANALYSIS_GROUP"] != "not_in_four_group_comparison", "ANALYSIS_GROUP"].unique().tolist()
    )
    selected_group = st.selectbox(
        "Comparison group",
        group_options,
        format_func=lambda value: value if value == "All assigned groups" else group_display(value),
        key=f"{key_prefix}_group",
    )
    pool = frame.loc[frame["ANALYSIS_GROUP"] != "not_in_four_group_comparison"].copy()
    if selected_group != "All assigned groups":
        pool = pool.loc[pool["ANALYSIS_GROUP"] == selected_group]
    profile_id = st.selectbox("Anonymous profile", pool["PROFILE_ID"].tolist(), key=f"{key_prefix}_profile")
    return frame.loc[frame["PROFILE_ID"] == profile_id].iloc[0]


def horizon_selector(key: str, manifest: dict) -> int:
    horizons = manifest.get(
        "time_horizons",
        [
            {"months": 1, "label": "1 month"},
            {"months": 6, "label": "6 months"},
            {"months": 12, "label": "1 year"},
            {"months": 24, "label": "2 years"},
        ],
    )
    options = [int(item["months"]) for item in horizons]
    labels = {int(item["months"]): item["label"] for item in horizons}
    default_index = options.index(12) if 12 in options else 0
    return st.selectbox(
        "Projected time",
        options,
        index=default_index,
        format_func=lambda value: labels[value],
        key=key,
    )


def render_vector_metrics(vector: dict[str, float | None], deltas: dict[str, float | None] | None = None):
    columns = st.columns(5)
    for column, dimension in zip(columns, DIMENSIONS):
        value = vector.get(dimension)
        delta = None if deltas is None else deltas.get(dimension)
        column.metric(
            DIMENSION_LABELS[dimension],
            "Missing" if value is None or pd.isna(value) else f"{float(value):.2f}",
            None if delta is None or pd.isna(delta) else f"{float(delta):+.2f}",
        )


def render_source_footer():
    st.markdown(
        """
        <div style="margin-top:2rem;padding-top:0.8rem;border-top:1px solid #e5e7eb;
                    font-size:0.78rem;color:#6b7280;line-height:1.45;">
        <strong>Evidence foundation:</strong> baseline calibrated with
        <a href="https://www.oecd.org/en/data/datasets/pisa-2022-database.html" target="_blank">OECD PISA 2022</a>
        public-use microdata for South Korea. Transparent policy-scenario design is inspired by
        <a href="https://www.unesco.org/en/articles/unescos-simued-50-offers-new-insights-and-solutions-education-sector-planning" target="_blank">UNESCO SimuED</a>.
        This is an independent student research model, not an OECD or UNESCO product. Policy outputs are
        transparent scenarios under stated assumptions, not diagnoses or guaranteed individual predictions.
        </div>
        """,
        unsafe_allow_html=True,
    )


def time_pathway_results(row, profiles, model_manifest, intervention_manifest, intervention_key, scenario, quality, dosage):
    horizons = intervention_manifest.get("time_horizons", [])
    results = []
    for horizon in horizons:
        months = int(horizon["months"])
        result = simulate_intervention(
            row,
            profiles,
            model_manifest,
            intervention_manifest,
            intervention_key,
            SimulationOptions(scenario, quality, dosage, months),
        )
        result["time_label"] = horizon["label"]
        results.append(result)
    return results


def time_pathway_frame(results: list[dict]) -> pd.DataFrame:
    rows = []
    for result in results:
        for dimension in DIMENSIONS:
            rows.append(
                {
                    "months": result["horizon_months"],
                    "time": result["time_label"],
                    "dimension": DIMENSION_LABELS[dimension],
                    "score": result["projected_vector"].get(dimension),
                    "change": result["vector_change"].get(dimension),
                    "time_factor": result["time_factor"],
                }
            )
    return pd.DataFrame(rows)


def axis_title(metadata: dict) -> str:
    return (
        f"{metadata['display_name']}<br>"
        f"<sup>{metadata['explained_variance_ratio']:.1%} of variation</sup>"
    )


st.title("EduBridge")
st.caption("Mathematical Education Model · South Korea · OECD PISA 2022 baseline")

root = st.sidebar.text_input("Project folder", value=str(Path.cwd()))
try:
    data = get_project_data(root)
except (FileNotFoundError, ValueError) as exc:
    st.error(str(exc))
    st.stop()

profiles = data.profiles
assigned_count = int((profiles["ANALYSIS_GROUP"] != "not_in_four_group_comparison").sum())
st.sidebar.success("Model files loaded")
st.sidebar.metric("Anonymous profiles", f"{len(profiles):,}")
st.sidebar.metric("Four-group profiles", f"{assigned_count:,}")
st.sidebar.caption("Scores are Korea-relative percentiles, not percentages of sufficiency.")

(
    overview_tab,
    student_tab,
    intervention_tab,
    map_tab,
    method_tab,
) = st.tabs(
    [
        "Group overview",
        "Student explorer",
        "Intervention simulator",
        "Population map",
        "Methods & evidence",
    ]
)

with overview_tab:
    st.subheader("Four comparison-group archetypes")
    st.write(
        "Each value is the survey-weighted median within a narrow comparison group. The middle family-background "
        "half and ambiguous town category are not included in these four archetypes."
    )
    archetypes = data.archetypes.copy()
    archetypes["Dimension"] = archetypes["dimension"].map(DIMENSION_LABELS)
    figure = px.bar(
        archetypes,
        x="Dimension",
        y="weighted_median",
        color="GROUP_LABEL",
        barmode="group",
        error_y="standard_error",
        labels={"weighted_median": "Weighted median percentile", "GROUP_LABEL": "Group"},
    )
    figure.update_yaxes(range=[0, 100])
    figure.update_layout(height=520)
    st.plotly_chart(figure, use_container_width=True)

    wide = archetypes_wide(data.archetypes)
    selected_group = st.selectbox("Inspect one archetype", wide["group"].tolist(), format_func=group_display)
    archetype = wide.loc[wide["group"] == selected_group].iloc[0]
    vector = {dimension: float(archetype[dimension]) for dimension in DIMENSIONS}
    left, right = st.columns(2)
    with left:
        st.plotly_chart(radar_figure(vector, group_display(selected_group)), use_container_width=True)
    with right:
        st.plotly_chart(vector_bar(vector, "Exact archetype values"), use_container_width=True)

with student_tab:
    st.subheader("Inspect an anonymous PISA-derived profile")
    st.write("A profile is statistically traceable but is not a diagnosis or a complete life story.")
    row = select_profile(profiles, "student")
    vector = {dimension: float(row[dimension]) for dimension in DIMENSIONS}
    st.markdown(f"**{row['PROFILE_ID']}** · {group_display(row['ANALYSIS_GROUP'])}")
    left, right = st.columns(2)
    with left:
        st.plotly_chart(radar_figure(vector, "Five-vector shape"), use_container_width=True)
    with right:
        st.plotly_chart(vector_bar(vector, "Five-vector values"), use_container_width=True)
    st.subheader("Indicator-level calculation trace")
    st.dataframe(profile_indicator_table(row, data.model_manifest), use_container_width=True, hide_index=True)

with intervention_tab:
    st.subheader("How one intervention changes one student's state over time")
    st.write(
        "The time curve describes gradual implementation and adoption of the evidence-defined endpoint. "
        "It does not claim that every child's development follows the same biological law."
    )
    row = select_profile(profiles, "intervention")
    profile_id = str(row["PROFILE_ID"])
    baseline_vector = {dimension: float(row[dimension]) for dimension in DIMENSIONS}

    st.markdown(f"### Current state · {profile_id}")
    baseline_left, baseline_right = st.columns(2)
    with baseline_left:
        st.plotly_chart(radar_figure(baseline_vector, "Current five-vector shape"), use_container_width=True)
    with baseline_right:
        st.plotly_chart(vector_bar(baseline_vector, "Current five-vector values"), use_container_width=True)
    render_vector_metrics(baseline_vector)

    st.divider()
    enabled = list_interventions(data.intervention_manifest)
    enabled = enabled.loc[enabled["enabled"]]
    with st.form("intervention_controls_v47"):
        selected_key = st.selectbox(
            "Intervention",
            enabled["intervention"].tolist(),
            format_func=lambda key: data.intervention_manifest["interventions"][key]["label"],
        )
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            scenario = st.selectbox("Evidence scenario", ["conservative", "central", "optimistic"], index=1)
        with c2:
            quality = st.slider("Implementation quality", 0.0, 1.0, 1.0, 0.05)
        with c3:
            dosage = st.slider("Programme dosage", 0.0, 1.0, 1.0, 0.05)
        with c4:
            horizon = horizon_selector("intervention_horizon_v47", data.intervention_manifest)
        submitted = st.form_submit_button("Apply intervention", type="primary", use_container_width=True)

    if submitted:
        selected_result = simulate_intervention(
            row,
            profiles,
            data.model_manifest,
            data.intervention_manifest,
            selected_key,
            SimulationOptions(scenario, quality, dosage, horizon),
        )
        selected_result["dimension_statuses"] = vector_change_statuses(selected_result)
        pathway = time_pathway_results(
            row,
            profiles,
            data.model_manifest,
            data.intervention_manifest,
            selected_key,
            scenario,
            quality,
            dosage,
        )
        st.session_state["phase47_simulation"] = {
            "profile_id": profile_id,
            "key": selected_key,
            "result": selected_result,
            "pathway": pathway,
        }

    stored = st.session_state.get("phase47_simulation")
    if stored and stored.get("profile_id") != profile_id:
        st.session_state.pop("phase47_simulation", None)
        stored = None

    if not stored:
        st.info("Choose an intervention and press **Apply intervention**. The projected vector and full time pathway will appear.")
    else:
        result = stored["result"]
        intervention_spec = data.intervention_manifest["interventions"][stored["key"]]
        st.divider()
        selected_label = next(
            item["label"]
            for item in data.intervention_manifest["time_horizons"]
            if int(item["months"]) == int(result["horizon_months"])
        )
        st.markdown(f"### Projected state after {selected_label}: {result['label']}")
        projected_left, projected_right = st.columns(2)
        with projected_left:
            st.plotly_chart(radar_figure(result["projected_vector"], "Projected five-vector shape"), use_container_width=True)
        with projected_right:
            st.plotly_chart(vector_bar(result["projected_vector"], "Projected five-vector values"), use_container_width=True)
        render_vector_metrics(result["projected_vector"], result["vector_change"])

        st.markdown("### Projected pathway: 1 month → 2 years")
        pathway_frame = time_pathway_frame(stored["pathway"])
        pathway_chart = px.line(
            pathway_frame,
            x="months",
            y="score",
            color="dimension",
            markers=True,
            labels={
                "months": "Months after intervention begins",
                "score": "Projected Korea-relative percentile",
                "dimension": "Dimension",
            },
        )
        pathway_chart.update_xaxes(tickmode="array", tickvals=[1, 6, 12, 24], ticktext=["1 month", "6 months", "1 year", "2 years"])
        pathway_chart.update_yaxes(range=[0, 100])
        pathway_chart.update_layout(height=500)
        st.plotly_chart(pathway_chart, use_container_width=True)

        pathway_table = pathway_frame.pivot(index="time", columns="dimension", values="score").reindex(
            ["1 month", "6 months", "1 year", "2 years"]
        )
        st.dataframe(pathway_table.round(2), use_container_width=True)
        st.caption(
            f"Time response: G(t) = 1 − 2^(−t/h), with h = {intervention_spec.get('time_half_life_months')} months for this intervention. "
            "At h months, half of the modelled endpoint is realised."
        )

        statuses = pd.DataFrame(result["dimension_statuses"])
        st.subheader("Why each dimension changed—or did not")
        st.dataframe(statuses, use_container_width=True, hide_index=True)
        st.subheader("Underlying indicator movement")
        st.dataframe(pd.DataFrame(result["indicator_changes"]), use_container_width=True, hide_index=True)
        with st.expander("Method, assumptions, and warnings", expanded=True):
            st.write(result.get("method", ""))
            st.write(intervention_spec.get("time_note", ""))
            for item in result.get("assumptions", []):
                st.write(f"- {item}")
            for item in result.get("warnings", []):
                st.warning(item)

with map_tab:
    st.subheader("Population map of five-vector profiles")
    st.write(
        "The map compresses the five original vectors into two or three summary axes. Each axis is labelled from "
        "the dimensions that contribute most strongly; it is not a new PISA variable."
    )
    c1, c2 = st.columns([1, 2])
    with c1:
        components = st.radio("View", [2, 3], horizontal=True, format_func=lambda n: f"{n}D")
        max_points = st.slider("Maximum plotted profiles", 500, min(5000, len(profiles)), min(2000, len(profiles)), 250)
        assigned_only = st.checkbox("Four comparison groups only", value=False)
    with c2:
        selected_id = st.selectbox("Highlight profile", profiles["PROFILE_ID"].tolist(), key="map_profile")

    embedding, explained, axis_metadata = compute_population_embedding(
        profiles,
        components=components,
        max_points=max_points,
        include_profile_id=selected_id,
        assigned_only=assigned_only,
        include_metadata=True,
    )
    hover = {dimension: ":.1f" for dimension in DIMENSIONS}
    if components == 2:
        figure = px.scatter(
            embedding,
            x="PC1",
            y="PC2",
            color="GROUP_LABEL",
            hover_name="PROFILE_ID",
            hover_data=hover,
            opacity=0.65,
        )
        figure.update_xaxes(title=axis_title(axis_metadata[0]))
        figure.update_yaxes(title=axis_title(axis_metadata[1]))
    else:
        figure = px.scatter_3d(
            embedding,
            x="PC1",
            y="PC2",
            z="PC3",
            color="GROUP_LABEL",
            hover_name="PROFILE_ID",
            hover_data=hover,
            opacity=0.65,
        )
        figure.update_layout(
            scene={
                "xaxis_title": axis_title(axis_metadata[0]),
                "yaxis_title": axis_title(axis_metadata[1]),
                "zaxis_title": axis_title(axis_metadata[2]),
            }
        )
    figure.update_layout(height=680)
    st.plotly_chart(figure, use_container_width=True)

    st.markdown("### What the axes mean")
    axis_rows = []
    for item in axis_metadata:
        axis_rows.append(
            {
                "Axis": item["display_name"],
                "Positive direction": item["positive_direction"],
                "Negative direction": item["negative_direction"],
                "Share of variation": f"{item['explained_variance_ratio']:.1%}",
            }
        )
    st.dataframe(pd.DataFrame(axis_rows), use_container_width=True, hide_index=True)

    with st.expander("See exact dimension loadings"):
        loading_rows = []
        for item in axis_metadata:
            for dimension, loading in item["loadings"].items():
                loading_rows.append(
                    {
                        "Axis": item["display_name"],
                        "Dimension": DIMENSION_LABELS[dimension],
                        "Loading": loading,
                    }
                )
        st.dataframe(pd.DataFrame(loading_rows).round(3), use_container_width=True, hide_index=True)

with method_tab:
    st.subheader("Intervention evidence registry")
    st.dataframe(data.evidence, use_container_width=True, hide_index=True)
    st.subheader("Enabled and disabled interventions")
    intervention_table = list_interventions(data.intervention_manifest)
    intervention_table["time_half_life_months"] = intervention_table["intervention"].map(
        lambda key: data.intervention_manifest["interventions"][key].get("time_half_life_months")
    )
    st.dataframe(intervention_table, use_container_width=True, hide_index=True)

    st.subheader("Time mathematics")
    st.latex(r"G_a(t)=1-2^{-t/h_a}")
    st.latex(r"\text{implemented strength}=q\times d\times G_a(t)")
    st.write(
        "Here, t is months, hₐ is the intervention-specific half-time, q is implementation quality, and d is dosage. "
        "The curve is strictly increasing and approaches the endpoint without exceeding it. Distinct time points "
        "therefore produce distinct states for responsive profiles. If a baseline indicator is missing or a student "
        "already meets the target, forcing artificial movement would be scientifically incorrect."
    )

    st.subheader("Model boundaries")
    st.write(
        "PISA scores describe relative opportunity conditions. Policy outputs are transparent scenarios under explicit "
        "assumptions. The 2-year values may extend beyond the evidence follow-up for some interventions and are labelled "
        "as persistence/adoption scenarios rather than proven long-term causal effects."
    )

render_source_footer()
