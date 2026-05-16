#!/usr/bin/env python3
"""
Genera graficas para la solucion del Job Shop Scheduling Problem (JSSP):
- Diagrama de Gantt por maquina.
- Curva de convergencia de la Busqueda Tabu.

Ejecutar:
    python3 plot_jssp_solution.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from jssp_tabu import (
    MAX_ITERATIONS,
    MAX_NO_IMPROVEMENT,
    NEIGHBORHOOD_SIZE,
    RANDOM_SEED,
    TABU_MAX,
    TABU_MIN,
    ScheduledOperation,
    demo_instance,
    tabu_search_jssp,
)


JOB_COLORS: Dict[int, str] = {
    1: "#1f77b4",
    2: "#d62728",
    3: "#2ca02c",
    4: "#9467bd",
    5: "#ff7f0e",
}


def plot_gantt_by_machine(
    schedule: List[ScheduledOperation],
    makespan: int,
    output_path: Path,
) -> None:
    """Genera el diagrama de Gantt por maquina."""
    machines = sorted({operation.machine_id for operation in schedule})
    fig, ax = plt.subplots(figsize=(12, 6.5))
    bar_height = 0.55

    for machine_id in machines:
        y_position = len(machines) - machine_id + 1
        machine_operations = sorted(
            [operation for operation in schedule if operation.machine_id == machine_id],
            key=lambda operation: operation.start,
        )

        for operation in machine_operations:
            color = JOB_COLORS[operation.job_id]
            duration = operation.finish - operation.start
            ax.barh(
                y_position,
                duration,
                left=operation.start,
                height=bar_height,
                color=color,
                edgecolor="#222222",
                alpha=0.9,
            )
            ax.text(
                operation.start + duration / 2,
                y_position,
                f"J{operation.job_id}-O{operation.op_id + 1}",
                ha="center",
                va="center",
                color="white",
                fontsize=9,
                weight="bold",
            )

    ax.axvline(makespan, color="#111111", linestyle="--", linewidth=1.6)
    ax.text(
        makespan,
        len(machines) + 0.55,
        f"Cmax = {makespan}",
        ha="right",
        va="center",
        fontsize=10,
        weight="bold",
    )

    ax.set_title("Diagrama de Gantt JSSP por maquina", fontsize=14, weight="bold")
    ax.set_xlabel("Tiempo")
    ax.set_ylabel("Maquina")
    ax.set_yticks(range(1, len(machines) + 1))
    ax.set_yticklabels([f"M{machine_id}" for machine_id in reversed(machines)])
    ax.set_xlim(0, makespan * 1.10)
    ax.grid(True, axis="x", linestyle="--", linewidth=0.5, alpha=0.45)
    ax.legend(
        handles=[
            Patch(facecolor=color, edgecolor="#222222", label=f"Trabajo {job_id}")
            for job_id, color in JOB_COLORS.items()
        ],
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_convergence(history: List[tuple], output_path: Path) -> None:
    """Genera la curva de convergencia del mejor Cmax historico."""
    fig, ax = plt.subplots(figsize=(10, 5.5))

    if history:
        iterations = [item[0] for item in history]
        best_values = [item[1] for item in history]
        ax.plot(iterations, best_values, color="#1f77b4", linewidth=2.2)
        ax.scatter(iterations[-1], best_values[-1], color="#d62728", zorder=4)
        ax.annotate(
            f"Mejor Cmax = {best_values[-1]}",
            (iterations[-1], best_values[-1]),
            xytext=(-110, 18),
            textcoords="offset points",
            fontsize=10,
            weight="bold",
            arrowprops={"arrowstyle": "->", "color": "#333333"},
        )

    ax.set_title("Convergencia de la Busqueda Tabu para JSSP", fontsize=14, weight="bold")
    ax.set_xlabel("Iteracion")
    ax.set_ylabel("Mejor Cmax historico")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.45)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    jobs, machines = demo_instance()
    result = tabu_search_jssp(
        jobs,
        machines,
        max_iterations=MAX_ITERATIONS,
        max_no_improvement=MAX_NO_IMPROVEMENT,
        tabu_min=TABU_MIN,
        tabu_max=TABU_MAX,
        neighborhood_size=NEIGHBORHOOD_SIZE,
        seed=RANDOM_SEED,
    )

    output_dir = Path("figures")
    output_dir.mkdir(parents=True, exist_ok=True)

    gantt_path = output_dir / "jssp_gantt_maquinas.png"
    convergence_path = output_dir / "jssp_convergencia.png"

    schedule = result["schedule"]
    history = result["history"]
    makespan = result["makespan"]
    assert isinstance(schedule, list)
    assert isinstance(history, list)
    assert isinstance(makespan, int)

    plot_gantt_by_machine(schedule, makespan, gantt_path)
    plot_convergence(history, convergence_path)

    print(f"Makespan Cmax: {makespan}")
    print(f"Diagrama de Gantt JSSP: {gantt_path}")
    print(f"Curva de convergencia: {convergence_path}")


if __name__ == "__main__":
    main()
